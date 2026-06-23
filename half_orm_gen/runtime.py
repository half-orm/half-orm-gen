"""
Dynamic Litestar application builder from a halfORM model.

Replaces code-generated api/app.py route handlers with runtime-constructed
closures. No TypedDicts, no per-relation files — routes are registered at
server startup by reading CRUD_ACCESS from relation modules.
"""
import importlib
import re
import sys
import uuid
import datetime
import decimal
from typing import Optional, List, Any

from litestar import Litestar, get, post, put, delete, websocket, Request, WebSocket
from litestar.exceptions import HTTPException
from litestar.logging import LoggingConfig


# ---------------------------------------------------------------------------
# Shared WebSocket manager
# ---------------------------------------------------------------------------

class _ConnectionManager:
    def __init__(self):
        self._sockets: set = set()

    async def connect(self, socket: WebSocket) -> None:
        await socket.accept()
        self._sockets.add(socket)

    def disconnect(self, socket: WebSocket) -> None:
        self._sockets.discard(socket)

    async def broadcast(self, message: dict) -> None:
        import json as _json
        dead = set()
        for s in set(self._sockets):
            try:
                await s.send_data(_json.dumps(message, default=str))
            except Exception:
                dead.add(s)
        self._sockets -= dead


_manager = _ConnectionManager()


# ---------------------------------------------------------------------------
# Role / access helpers  (same logic as CRUD_HELPERS template)
# ---------------------------------------------------------------------------

def _get_roles(request: Request) -> list[str]:
    roles = getattr(request.state, 'authorized_roles', None)
    if roles is not None:
        return roles
    token = request.headers.get('Authorization', '').removeprefix('Bearer ').strip()
    return [token] if token else ['public']


def _get_role_filter(crud_access: dict, verb: str, authorized_roles: list[str]) -> dict:
    role_map = crud_access.get(verb, {})
    combined = {}
    for role in authorized_roles:
        rv = role_map.get(role)
        if isinstance(rv, dict) and 'filter' in rv:
            combined.update(rv['filter'])
    return combined


def _effective_out_fields(
    crud_access: dict,
    verb: str,
    authorized_roles: list[str],
    api_excluded: list | None = None,
) -> list | None:
    api_excluded = api_excluded or []
    if 'ho_dev' in authorized_roles:
        return []
    role_map = crud_access.get(verb, {})
    get_map  = crud_access.get('GET', {})
    fields: list[str] = []
    for role in authorized_roles:
        if role not in role_map:
            return None
        rv = role_map[role]
        if isinstance(rv, dict):
            out = rv.get('out') if 'out' in rv else (
                get_map.get(role) if not isinstance(get_map.get(role), dict)
                else get_map.get(role, {}).get('out')
            )
        else:
            out = rv
        if out is None:
            return []
        fields.extend(out)
    return [f for f in dict.fromkeys(fields) if f not in api_excluded]


def _effective_in_fields(
    crud_access: dict,
    verb: str,
    authorized_roles: list[str],
    api_excluded: list | None = None,
) -> list:
    api_excluded = api_excluded or []
    role_map = crud_access.get(verb, {})
    fields: list[str] = []
    for role in authorized_roles:
        rv = role_map.get(role)
        if rv is None or not isinstance(rv, dict):
            return []
        in_val = rv.get('in')
        if in_val is None:
            return []
        fields.extend(in_val)
    return [f for f in dict.fromkeys(fields) if f not in api_excluded]


def _resolved_out(crud_access: dict, verb: str, role: str):
    rv = crud_access.get(verb, {}).get(role)
    if verb in ('GET', 'DELETE'):
        return rv
    if not isinstance(rv, dict):
        return None
    if 'out' in rv:
        return rv['out']
    get_rv = crud_access.get('GET', {}).get(role)
    return get_rv if not isinstance(get_rv, dict) else get_rv.get('out')


def _resolved_in(crud_access: dict, verb: str, role: str):
    rv = crud_access.get(verb, {}).get(role)
    if not isinstance(rv, dict):
        return None
    return rv.get('in')


# ---------------------------------------------------------------------------
# Composite PK helpers
# ---------------------------------------------------------------------------

_COMPOSITE_PK_PATTERN = r'^[a-zA-Z_][a-zA-Z0-9_]*:[^:]+(::[a-zA-Z_][a-zA-Z0-9_]*:[^:]+)*$'


def _parse_composite_pk(pk_str: str, expected_cols: list[str]) -> dict[str, str]:
    if not re.match(_COMPOSITE_PK_PATTERN, pk_str):
        raise HTTPException(
            status_code=400,
            detail=f'Invalid composite PK format. Expected col:val::col:val, got: {pk_str}',
        )
    try:
        parts = pk_str.split('::')
        parsed = {col: val for col, val in (part.split(':', 1) for part in parts)}
    except ValueError:
        raise HTTPException(status_code=400, detail=f'Invalid composite PK: {pk_str}')
    if set(parsed.keys()) != set(expected_cols):
        raise HTTPException(
            status_code=400,
            detail=f'Invalid PK columns. Expected: {expected_cols}, got: {list(parsed.keys())}',
        )
    return parsed


# ---------------------------------------------------------------------------
# PK introspection
# ---------------------------------------------------------------------------

_KNOWN_PY_TYPES = {
    uuid.UUID:          'uuid.UUID',
    int:                'int',
    str:                'str',
    float:              'float',
    decimal.Decimal:    'decimal.Decimal',
    datetime.date:      'datetime.date',
    datetime.datetime:  'datetime.datetime',
    datetime.time:      'datetime.time',
    datetime.timedelta: 'datetime.timedelta',
}

_LITESTAR_PATH_TYPE_MAP = {
    'uuid.UUID':          'uuid',
    'int':                'int',
    'str':                'str',
    'float':              'float',
    'decimal.Decimal':    'decimal',
    'datetime.date':      'date',
    'datetime.datetime':  'datetime',
    'datetime.time':      'time',
    'datetime.timedelta': 'timedelta',
}


def _py_type_str(py_type) -> str:
    return _KNOWN_PY_TYPES.get(py_type, str(py_type))


def _pk_info(cls) -> list[tuple[str, str]]:
    """Return [(field_name, litestar_path_type), ...] for PK columns."""
    pkey = getattr(cls(), '_ho_pkey', {})
    result = []
    for name, obj in pkey.items():
        type_str = _py_type_str(obj.py_type)
        litestar_type = _LITESTAR_PATH_TYPE_MAP.get(type_str, 'str')
        result.append((name, litestar_type))
    return result


# ---------------------------------------------------------------------------
# Search-query parser  (reused by list handlers)
# ---------------------------------------------------------------------------

def _parse_q(
    q: str, api_excluded: list[str]
) -> tuple[dict, list[str], list]:
    filter_kwargs: dict = {}
    search_cols: list[str] = []
    range_filters: list = []
    for pair in q.split(','):
        if ':' not in pair:
            continue
        col, val = pair.split(':', 1)
        col, val = col.strip(), val.strip()
        if not col or not val or col in api_excluded:
            continue
        range_match = re.match(r'^(>=|>)(.+?)(<=|<)(.+)$', val)
        if range_match:
            op1, op1val, op2, op2val = range_match.groups()
            if op1val.strip() and op2val.strip():
                range_filters.append((col, op1, op1val.strip(), op2, op2val.strip()))
        else:
            single = re.match(r'^(>=|>|<=|<)(.*)$', val)
            if single:
                op, operand = single.groups()
                if operand.strip():
                    filter_kwargs[col] = (op, operand.strip())
            else:
                filter_kwargs[col] = ('ilike', val + '%')
                search_cols.append(col)
    return filter_kwargs, search_cols, range_filters


# ---------------------------------------------------------------------------
# Route handler factories
# Decorator applied AFTER __name__/__qualname__ are set so Litestar picks up
# the unique name when building operation_ids for OpenAPI.
# ---------------------------------------------------------------------------

def _make_list_handler(path: str, cls, crud_access: dict, api_excluded: list, resource: str):
    slug = resource.replace('/', '_')

    async def handler(
        request: Request,
        fields: Optional[List[str]] = None,
        limit: Optional[int] = 100,
        offset: Optional[int] = 0,
        q: Optional[str] = None,
    ) -> dict:
        roles = _get_roles(request)
        filter_kwargs: dict = {}
        search_cols: list[str] = []
        range_filters: list = []
        if q:
            filter_kwargs, search_cols, range_filters = _parse_q(q, api_excluded)
        role_filter = _get_role_filter(crud_access, 'GET', roles)
        authorized = _effective_out_fields(crud_access, 'GET', roles, api_excluded)
        if authorized is None:
            return {'data': [], 'meta': {'offset': offset, 'limit': limit, 'has_more': False}}
        projection = [f for f in fields if not authorized or f in authorized] if fields else authorized
        inst = cls(**{**filter_kwargs, **role_filter})
        for col, op1, op1val, op2, op2val in range_filters:
            field = getattr(inst, col)
            if op1 == '>=':
                field >= op1val
            else:
                field > op1val
            if op2 == '<=':
                field <= op2val
            else:
                field < op2val
        for col in search_cols:
            getattr(inst, col).unaccent = True
        data = await inst.ho_aselect(*(projection or []), limit=limit, offset=offset)
        return {'data': data, 'meta': {'offset': offset, 'limit': limit, 'has_more': len(data) == limit}}

    handler.__name__ = handler.__qualname__ = f'list_{slug}'
    return get(path)(handler)


def _make_get_handler(
    path: str, cls, crud_access: dict, api_excluded: list,
    pk_info: list[tuple[str, str]], resource: str,
):
    pk_names = [p[0] for p in pk_info]
    is_simple = len(pk_names) == 1
    pk_name = pk_info[0][0]
    slug = resource.replace('/', '_')

    async def handler(request: Request, id: str) -> dict:
        roles = _get_roles(request)
        role_filter = _get_role_filter(crud_access, 'GET', roles)
        authorized = _effective_out_fields(crud_access, 'GET', roles, api_excluded)
        if authorized is None:
            raise HTTPException(status_code=403)
        pk_filter = {pk_name: id} if is_simple else _parse_composite_pk(id, pk_names)
        rows = await cls(**{**pk_filter, **role_filter}).ho_aselect(*(authorized or []))
        if not rows:
            raise HTTPException(status_code=404)
        return rows[0]

    handler.__name__ = handler.__qualname__ = f'get_{slug}'
    return get(f'{path}/{{id:str}}')(handler)


def _make_post_handler(
    path: str, cls, crud_access: dict, api_excluded: list,
    resource: str, pk_name: str,
):
    slug = resource.replace('/', '_')

    async def handler(request: Request, data: dict[str, Any]) -> dict:
        roles = _get_roles(request)
        in_fields = _effective_in_fields(crud_access, 'POST', roles, api_excluded)
        payload = {
            k: v for k, v in data.items()
            if v is not None and (not in_fields or k in in_fields)
        }
        result = await cls(**payload).ho_ainsert()
        pk_val = result.get(pk_name, '') if result else ''
        await _manager.broadcast({'event': 'create', 'resource': resource, 'id': str(pk_val)})
        return result

    handler.__name__ = handler.__qualname__ = f'create_{slug}'
    return post(path)(handler)


def _make_put_handler(
    path: str, cls, crud_access: dict, api_excluded: list,
    pk_info: list[tuple[str, str]], resource: str,
):
    pk_names = [p[0] for p in pk_info]
    is_simple = len(pk_names) == 1
    pk_name = pk_info[0][0]
    slug = resource.replace('/', '_')

    async def handler(request: Request, id: str, data: dict[str, Any]) -> dict:
        roles = _get_roles(request)
        in_fields = _effective_in_fields(crud_access, 'PUT', roles, api_excluded)
        authorized = _effective_out_fields(crud_access, 'PUT', roles, api_excluded)
        payload = {
            k: v for k, v in data.items()
            if v is not None and (not in_fields or k in in_fields)
        }
        pk_filter = {pk_name: id} if is_simple else _parse_composite_pk(id, pk_names)
        result = await cls(**pk_filter).ho_aupdate(*(authorized or ['*']), **payload)
        if not result:
            raise HTTPException(status_code=404)
        await _manager.broadcast({'event': 'update', 'resource': resource, 'id': str(id)})
        return result[0]

    handler.__name__ = handler.__qualname__ = f'update_{slug}'
    return put(f'{path}/{{id:str}}')(handler)


def _make_delete_handler(
    path: str, cls, crud_access: dict, api_excluded: list,
    pk_info: list[tuple[str, str]], resource: str, ws_rmap: dict,
):
    pk_names = [p[0] for p in pk_info]
    is_simple = len(pk_names) == 1
    pk_name = pk_info[0][0]
    slug = resource.replace('/', '_')

    async def handler(request: Request, id: str) -> None:
        pk_filter = {pk_name: id} if is_simple else _parse_composite_pk(id, pk_names)
        inst = cls(**pk_filter)
        await _ws_broadcast_cascade(inst, resource, id, ws_rmap)
        result = await inst.ho_adelete('*')
        if not result:
            raise HTTPException(status_code=404)
        await _manager.broadcast({'event': 'delete', 'resource': resource, 'id': str(id)})

    handler.__name__ = handler.__qualname__ = f'delete_{slug}'
    return delete(f'{path}/{{id:str}}')(handler)


async def _ws_broadcast_cascade(
    inst, resource: str, pk_val, ws_rmap: dict, _seen: set | None = None
) -> None:
    if _seen is None:
        _seen = set()
    _key = (resource, str(pk_val))
    if _key in _seen:
        return
    _seen.add(_key)
    for fk in inst._ho_fkeys.values():
        if not fk.is_reverse or len(fk.fk_names) != 1:
            continue
        fk_field = fk.fk_names[0]
        fqtn = fk.remote['fqtn']
        child_resource = f"{fqtn[0].replace('.', '_')}/{fqtn[1]}"
        if child_resource not in ws_rmap:
            continue
        child_cls, child_pk = ws_rmap[child_resource]
        for row in await child_cls(**{fk_field: pk_val}).ho_aselect(child_pk):
            rid = row[child_pk]
            await _ws_broadcast_cascade(child_cls(**{child_pk: rid}), child_resource, rid, ws_rmap, _seen)
            await _manager.broadcast({'event': 'delete', 'resource': child_resource, 'id': str(rid)})


# ---------------------------------------------------------------------------
# Access-map helpers  (used by /ho_access)
# ---------------------------------------------------------------------------

def _build_access_entry(crud_access: dict, api_excluded: list, all_field_names: list) -> dict:
    entry: dict = {}
    for verb in ('GET', 'POST', 'PUT', 'DELETE'):
        roles = crud_access.get(verb)
        if not roles:
            continue
        verb_entry: dict = {}
        for role, rv in roles.items():
            if verb == 'GET':
                out = rv if not isinstance(rv, dict) else rv.get('out')
                verb_entry[role] = {
                    'out': (
                        [f for f in all_field_names if f not in api_excluded]
                        if out is None else [f for f in out if f not in api_excluded]
                    )
                }
            elif verb == 'DELETE':
                verb_entry[role] = 'allowed'
            else:
                in_val = _resolved_in(crud_access, verb, role)
                out_val = _resolved_out(crud_access, verb, role)
                all_f = [f for f in all_field_names if f not in api_excluded]
                verb_entry[role] = {
                    'in':  all_f if in_val is None else [f for f in in_val if f not in api_excluded],
                    'out': all_f if out_val is None else [f for f in out_val if f not in api_excluded],
                }
        if verb_entry:
            entry[verb] = verb_entry
    return entry


def _filter_access_for_roles(access_map: dict, authorized_roles: list[str]) -> dict:
    result: dict = {}
    for resource, verbs in access_map.items():
        resource_entry: dict = {}
        for verb, roles in verbs.items():
            if verb == 'DELETE':
                if any(r in roles and roles[r] == 'allowed' for r in authorized_roles):
                    resource_entry[verb] = True
            else:
                active = {r: roles[r] for r in authorized_roles if r in roles}
                if not active:
                    continue
                if verb == 'GET':
                    out: list = []
                    for v in active.values():
                        out.extend(v.get('out', []))
                    resource_entry[verb] = {'out': list(dict.fromkeys(out))}
                else:
                    in_f: list = []
                    out_f: list = []
                    for v in active.values():
                        in_f.extend(v.get('in', []))
                        out_f.extend(v.get('out', []))
                    resource_entry[verb] = {
                        'in':  list(dict.fromkeys(in_f)),
                        'out': list(dict.fromkeys(out_f)),
                    }
        if resource_entry:
            result[resource] = resource_entry
    return result


# ---------------------------------------------------------------------------
# Special endpoint factories
# ---------------------------------------------------------------------------

def _make_ho_meta(model, prefix: str):
    @get(f'{prefix}/ho_meta')
    async def ho_meta() -> dict:
        return model.ho_meta()
    return ho_meta


def _make_ho_roles(roles_list: list, prefix: str):
    @get(f'{prefix}/ho_roles')
    async def ho_roles() -> list:
        return roles_list
    return ho_roles


def _make_ho_access(access_map: dict, model, prefix: str):
    @get(f'{prefix}/ho_access')
    async def ho_access(request: Request) -> dict:
        roles = _get_roles(request)
        return _filter_access_for_roles(access_map, roles)
    return ho_access


def _make_ws_handler(version_prefix: str):
    @websocket(f'{version_prefix}/ws')
    async def ws_handler(socket: WebSocket) -> None:
        await _manager.connect(socket)
        try:
            while True:
                await socket.receive_data(mode='text')
        except Exception:
            pass
        finally:
            _manager.disconnect(socket)
    return ws_handler


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

_HO_WARN = """
======================================================================
  halfORM DEV HELPERS ACTIVE — NOT FOR PRODUCTION
======================================================================
  /ho_roles  : exposes all declared roles (no authentication)
  /ho_access : exposes the full access map filtered by role
  _get_roles : bearer token used directly as a role name
               (no signature verification)
  ho_dev     : super-role with full access to all resources
               (Authorization: Bearer ho_dev)

  Replace the Authorization middleware with a real JWT implementation
  before deploying to production.
======================================================================
"""
_HO_WARN_SHOWN = False


def build_crud_app(
    model,
    module_name: str = '',
    api_version: int | None = None,
    middleware: list | None = None,
    **litestar_kwargs,
) -> Litestar:
    """
    Build a Litestar application dynamically from a halfORM model.

    Reads CRUD_ACCESS from relation modules at startup and registers
    routes programmatically — no code generation needed.
    """
    prefix = f'/v{api_version}' if api_version is not None else ''

    access_map: dict = {}
    roles_set: set[str] = {'ho_dev'}
    ws_rmap: dict = {}
    relation_handlers: list = []

    for cls, _kind in model.classes():
        mod = importlib.import_module(cls.__module__)
        crud_access = getattr(mod, 'CRUD_ACCESS', None)
        if not crud_access:
            crud_access = {'GET': {}, 'POST': {}, 'PUT': {}, 'DELETE': {}}

        api_excluded: list[str] = getattr(mod, 'API_EXCLUDED_FIELDS', [])

        inst = cls()
        schema = inst._t_fqrn[1]
        table  = inst._t_fqrn[2]
        resource = f'{schema}/{table}'
        path     = f'{prefix}/{resource}'
        pk_info  = _pk_info(cls)

        # Field names for access-map building
        sfqrn = inst._t_fqrn
        all_field_names = list(model._fields_metadata(sfqrn).keys())

        # Populate roles set
        for verb_roles in crud_access.values():
            if isinstance(verb_roles, dict):
                roles_set.update(verb_roles.keys())

        # Build access map entry
        access_entry = _build_access_entry(crud_access, api_excluded, all_field_names)

        # Add ho_dev entries when not in production
        if not model._production_mode and access_entry:
            all_f = [f for f in all_field_names if f not in api_excluded]
            for verb in ('GET', 'POST', 'PUT', 'DELETE'):
                if crud_access.get(verb):
                    verb_entry = dict(access_entry.get(verb, {}))
                    if verb == 'GET':
                        verb_entry['ho_dev'] = {'out': all_f}
                    elif verb == 'DELETE':
                        verb_entry['ho_dev'] = 'allowed'
                    else:
                        verb_entry['ho_dev'] = {'in': all_f, 'out': all_f}
                    access_entry[verb] = verb_entry

        if access_entry:
            access_map[resource] = access_entry

        # Register WS cascade entry (simple PK only)
        if pk_info and len(pk_info) == 1:
            ws_rmap[resource] = (cls, pk_info[0][0])

        # Build route handlers based on declared verbs
        has_get    = bool(crud_access.get('GET'))
        has_post   = bool(crud_access.get('POST'))
        has_put    = bool(crud_access.get('PUT'))
        has_delete = bool(crud_access.get('DELETE'))

        if has_get:
            relation_handlers.append(
                _make_list_handler(path, cls, crud_access, api_excluded, resource)
            )
            if pk_info:
                relation_handlers.append(
                    _make_get_handler(path, cls, crud_access, api_excluded, pk_info, resource)
                )

        if has_post and pk_info:
            relation_handlers.append(
                _make_post_handler(path, cls, crud_access, api_excluded, resource, pk_info[0][0])
            )

        if has_put and pk_info:
            relation_handlers.append(
                _make_put_handler(path, cls, crud_access, api_excluded, pk_info, resource)
            )

        if has_delete and pk_info:
            relation_handlers.append(
                _make_delete_handler(path, cls, crud_access, api_excluded, pk_info, resource, ws_rmap)
            )

    roles_list = sorted(roles_set - {'ho_dev'})

    special_handlers = [
        _make_ho_meta(model, prefix),
        _make_ho_roles(roles_list, prefix),
        _make_ho_access(access_map, model, prefix),
        _make_ws_handler(prefix),
    ]

    custom_handlers: list = []
    try:
        from api.custom.routes import routes as _custom
        custom_handlers = _custom
    except ImportError:
        pass

    logging_config = LoggingConfig(
        loggers={'app': {'level': 'ERROR', 'handlers': ['queue_listener']}}
    )

    async def _startup() -> None:
        global _HO_WARN_SHOWN
        await model.aconnect()
        if model._production_mode:
            raise RuntimeError(
                'halfORM DEV HELPERS are active (ho_roles, ho_access, _get_roles fallback). '
                'These routes and the bearer-token-as-role fallback are not safe for production. '
                'Secure or remove them before deploying.'
            )
        if not _HO_WARN_SHOWN:
            print(_HO_WARN, file=sys.stderr, flush=True)
            _HO_WARN_SHOWN = True

    return Litestar(
        route_handlers=special_handlers + relation_handlers + custom_handlers,
        middleware=middleware or [],
        logging_config=logging_config,
        on_startup=[_startup],
        **litestar_kwargs,
    )