"""
Dynamic Litestar application builder from a halfORM model.

Replaces code-generated api/app.py route handlers with runtime-constructed
closures. No TypedDicts, no per-relation files — routes are registered at
server startup by reading access configuration from "half_orm_meta.api" tables.
"""
import asyncio
import importlib
import re
import signal
import sys
from typing import Optional, List, Any

from litestar import Litestar, Router, get, post, put, delete, websocket, Request, WebSocket
from litestar.exceptions import HTTPException
from litestar.logging import LoggingConfig

from half_orm_gen.backend.ho_api.loader import (
    load_crud_access,
    load_role_parents,
    ensure_system_roles,
    reconcile_catalog,
)
from half_orm_gen.backend.crud_helpers import (
    _COMPOSITE_PK_PATTERN, _py_type_str,
    _get_roles, _get_role_filter, _get_active_filters,
    _effective_out_fields, _effective_in_fields,
    _resolved_out, _resolved_in,
    _parse_q, _build_access_entry, _filter_access_for_roles,
    _expand_roles,
    _ws_broadcast_cascade,
    _ws_event,
)


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
# Composite PK helpers  (_COMPOSITE_PK_PATTERN imported from crud_helpers)
# ---------------------------------------------------------------------------

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
# PK introspection  (_KNOWN_PY_TYPES and _py_type_str imported from crud_helpers)
# ---------------------------------------------------------------------------

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
# Route handler factories
#
# Each factory closes over:
#   - resource: str  (key into the dicts below)
#   - crud_access_by_res: dict[str, dict]  — populated at startup from DB
#   - api_excluded_by_res: dict[str, list] — populated at build time from Python modules
#   - all_fields_by_res: dict[str, list]   — all non-excluded fields per resource
# ---------------------------------------------------------------------------

def _make_list_handler(
    path: str, cls, resource: str,
    crud_access_by_res: dict, api_excluded_by_res: dict, all_fields_by_res: dict,
    parent_map_holder: list, pk_names: list | None = None,
):
    slug = resource.replace('/', '_')
    schema_name, table_name = resource.split('/')

    async def handler(
        request: Request,
        fields: Optional[List[str]] = None,
        limit: Optional[int] = 100,
        offset: Optional[int] = 0,
        q: Optional[str] = None,
    ) -> dict:
        from half_orm_gen.backend.ho_api.registry import _ROLE_REGISTRY, _FILTER_REGISTRY
        crud_access = crud_access_by_res.get(resource, {})
        api_excluded = api_excluded_by_res.get(resource, [])
        roles = _expand_roles(_get_roles(request), parent_map_holder[0])
        searchable_cols: set[str] = set()
        for role in roles:
            rv = crud_access.get('GET', {}).get(role, {})
            if isinstance(rv, dict):
                searchable_cols.update(rv.get('searchable', []))
        filter_kwargs: dict = {}
        search_cols: list[str] = []
        range_filters: list = []
        if q and not searchable_cols:
            return {'data': [], 'meta': {'offset': offset, 'limit': limit, 'has_more': False, 'dynamic_roles': {}}}
        if q:
            filter_kwargs, search_cols, range_filters = _parse_q(q, api_excluded)
            filter_kwargs  = {k: v for k, v in filter_kwargs.items()  if k in searchable_cols}
            search_cols    = [c for c in search_cols    if c in searchable_cols]
            range_filters  = [r for r in range_filters  if r[0] in searchable_cols]
        col_filters: dict = {
            k[7:]: v
            for k, v in request.query_params.items()
            if k.startswith('ho_col_') and k[7:] not in api_excluded
        }
        role_filter = _get_role_filter(crud_access, 'GET', roles)
        authorized = _effective_out_fields(crud_access, 'GET', roles, api_excluded, all_fields_by_res.get(resource, []), pk_names)
        if not authorized:
            raise HTTPException(status_code=403)
        projection = [f for f in fields if f in authorized] if fields else authorized
        inst = cls(**{**filter_kwargs, **col_filters, **role_filter})
        for filter_name in _get_active_filters(crud_access, 'GET', roles):
            fn = _FILTER_REGISTRY.get((schema_name, table_name, filter_name))
            if fn:
                inst = fn(inst, request) or inst
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
        dynamic_roles: dict = {}
        crud_access = crud_access_by_res.get(resource, {})
        _all_verbs = ('GET', 'POST', 'PUT', 'DELETE')
        dyn_methods = [
            (rn, fn) for (s, t, rn), fn in _ROLE_REGISTRY.items()
            if s == schema_name and t == table_name
            and any(rn in crud_access.get(v, {}) for v in _all_verbs)
        ]
        if dyn_methods and data and getattr(request.state, 'user', None):
            resolver_inst = cls()
            for role_name, fn in dyn_methods:
                pk_set = fn(resolver_inst, request, data)
                if pk_set:
                    role_data: dict = {
                        'ids': [str(pk) for pk in pk_set],
                        'verbs': [v for v in _all_verbs if role_name in crud_access.get(v, {})],
                    }
                    put_entry = crud_access.get('PUT', {}).get(role_name)
                    if isinstance(put_entry, dict):
                        role_data['put_in']  = put_entry.get('in', [])
                        role_data['put_out'] = put_entry.get('out', [])
                    dynamic_roles[role_name] = role_data
        meta: dict = {'offset': offset, 'limit': limit, 'has_more': len(data) == limit,
                      'dynamic_roles': dynamic_roles}
        return {'data': data, 'meta': meta}

    handler.__name__ = handler.__qualname__ = f'list_{slug}'
    return get(path)(handler)


def _make_get_handler(
    path: str, cls, resource: str,
    crud_access_by_res: dict, api_excluded_by_res: dict, all_fields_by_res: dict,
    pk_info: list[tuple[str, str]],
    parent_map_holder: list,
):
    pk_names = [p[0] for p in pk_info]
    is_simple = len(pk_names) == 1
    pk_name = pk_info[0][0]
    slug = resource.replace('/', '_')
    schema_name, table_name = resource.split('/')

    async def handler(request: Request, id: str) -> dict:
        from half_orm_gen.backend.ho_api.registry import _FILTER_REGISTRY
        crud_access = crud_access_by_res.get(resource, {})
        api_excluded = api_excluded_by_res.get(resource, [])
        roles = _expand_roles(_get_roles(request), parent_map_holder[0])
        role_filter = _get_role_filter(crud_access, 'GET', roles)
        authorized = _effective_out_fields(crud_access, 'GET', roles, api_excluded, all_fields_by_res.get(resource, []), pk_names)
        if not authorized:
            raise HTTPException(status_code=403)
        pk_filter = {pk_name: id} if is_simple else _parse_composite_pk(id, pk_names)
        inst = cls(**{**pk_filter, **role_filter})
        for filter_name in _get_active_filters(crud_access, 'GET', roles):
            fn = _FILTER_REGISTRY.get((schema_name, table_name, filter_name))
            if fn:
                inst = fn(inst, request) or inst
        rows = await inst.ho_aselect(*authorized)
        if not rows:
            raise HTTPException(status_code=404)
        return rows[0]

    handler.__name__ = handler.__qualname__ = f'get_{slug}'
    return get(f'{path}/{{id:str}}')(handler)


def _make_post_handler(
    path: str, cls, resource: str,
    crud_access_by_res: dict, api_excluded_by_res: dict, all_fields_by_res: dict,
    pk_name: str,
    parent_map_holder: list,
):
    slug = resource.replace('/', '_')

    async def handler(request: Request, data: dict[str, Any]) -> dict:
        crud_access = crud_access_by_res.get(resource, {})
        api_excluded = api_excluded_by_res.get(resource, [])
        roles = _expand_roles(_get_roles(request), parent_map_holder[0])
        if not crud_access.get('POST'):
            raise HTTPException(status_code=403)
        in_fields = _effective_in_fields(crud_access, 'POST', roles, api_excluded, all_fields_by_res.get(resource, []))
        if not in_fields:
            raise HTTPException(status_code=403)
        payload = {
            k: v for k, v in data.items()
            if v is not None and k in in_fields
        }
        fk_auto: dict = {}
        for role in roles:
            fa = crud_access.get('POST', {}).get(role, {})
            if isinstance(fa, dict):
                fk_auto.update(fa.get('fk_auto', {}))
        for field, rule in fk_auto.items():
            if rule == 'connected_user':
                payload.pop(field, None)
                user_raw = getattr(request.state, 'user', None)
                if isinstance(user_raw, dict):
                    user_id = user_raw.get('id')
                elif user_raw is not None:
                    user_id = str(user_raw)
                else:
                    user_id = None
                if user_id:
                    payload[field] = user_id
        result = await cls(**payload).ho_ainsert()
        pk_val = result.get(pk_name, '') if result else ''
        await _manager.broadcast(_ws_event('create', resource, pk_val))
        return result

    handler.__name__ = handler.__qualname__ = f'create_{slug}'
    return post(path)(handler)


def _make_put_handler(
    path: str, cls, resource: str,
    crud_access_by_res: dict, api_excluded_by_res: dict, all_fields_by_res: dict,
    pk_info: list[tuple[str, str]],
    parent_map_holder: list,
):
    pk_names = [p[0] for p in pk_info]
    is_simple = len(pk_names) == 1
    pk_name = pk_info[0][0]
    slug = resource.replace('/', '_')

    put_schema, put_table = resource.split('/')

    async def handler(request: Request, id: str, data: dict[str, Any]) -> dict:
        from half_orm_gen.backend.ho_api.registry import _ROLE_REGISTRY
        crud_access = crud_access_by_res.get(resource, {})
        api_excluded = api_excluded_by_res.get(resource, [])
        roles = _expand_roles(_get_roles(request), parent_map_holder[0])
        if not crud_access.get('PUT'):
            raise HTTPException(status_code=403)
        pk_filter = {pk_name: id} if is_simple else _parse_composite_pk(id, pk_names)
        dyn_methods = [(rn, fn) for (s, t, rn), fn in _ROLE_REGISTRY.items()
                       if s == put_schema and t == put_table]
        if dyn_methods and getattr(request.state, 'user', None):
            rows = await cls(**pk_filter).ho_aselect()
            if not rows:
                raise HTTPException(status_code=404)
            resolver_inst = cls()
            for role_name, fn in dyn_methods:
                pk_set = fn(resolver_inst, request, rows)
                if str(id) in {str(pk) for pk in pk_set}:
                    roles = list(dict.fromkeys(roles + [role_name]))
        in_fields = _effective_in_fields(crud_access, 'PUT', roles, api_excluded, all_fields_by_res.get(resource, []))
        authorized = _effective_out_fields(crud_access, 'PUT', roles, api_excluded, all_fields_by_res.get(resource, []))
        if not in_fields:
            raise HTTPException(status_code=403)
        payload = {
            k: v for k, v in data.items()
            if v is not None and k in in_fields
        }
        cols = authorized if authorized else ['*']
        result = await cls(**pk_filter).ho_aupdate(*cols, **payload)
        if not result:
            raise HTTPException(status_code=404)
        await _manager.broadcast(_ws_event('update', resource, id))
        return result[0] if authorized else {'ok': True, 'id': str(id)}

    handler.__name__ = handler.__qualname__ = f'update_{slug}'
    return put(f'{path}/{{id:str}}')(handler)


def _make_delete_handler(
    path: str, cls, resource: str,
    crud_access_by_res: dict, api_excluded_by_res: dict,
    pk_info: list[tuple[str, str]],
    ws_rmap: dict,
    parent_map_holder: list,
):
    pk_names = [p[0] for p in pk_info]
    is_simple = len(pk_names) == 1
    pk_name = pk_info[0][0]
    slug = resource.replace('/', '_')
    del_schema, del_table = resource.split('/')

    async def handler(request: Request, id: str) -> None:
        from half_orm_gen.backend.ho_api.registry import _ROLE_REGISTRY
        crud_access = crud_access_by_res.get(resource, {})
        roles = _expand_roles(_get_roles(request), parent_map_holder[0])
        if not crud_access.get('DELETE'):
            raise HTTPException(status_code=403)
        pk_filter = {pk_name: id} if is_simple else _parse_composite_pk(id, pk_names)
        dyn_methods = [(rn, fn) for (s, t, rn), fn in _ROLE_REGISTRY.items()
                       if s == del_schema and t == del_table]
        if dyn_methods and getattr(request.state, 'user', None):
            rows = await cls(**pk_filter).ho_aselect()
            if not rows:
                raise HTTPException(status_code=404)
            resolver_inst = cls()
            for role_name, fn in dyn_methods:
                pk_set = fn(resolver_inst, request, rows)
                if str(id) in {str(pk) for pk in pk_set}:
                    roles = list(dict.fromkeys(roles + [role_name]))
        if not any(r in crud_access.get('DELETE', {}) for r in roles):
            raise HTTPException(status_code=403)
        inst = cls(**pk_filter)
        await _ws_broadcast_cascade(inst, resource, id, ws_rmap, _manager.broadcast)
        result = await inst.ho_adelete('*')
        if not result:
            raise HTTPException(status_code=404)
        await _manager.broadcast(_ws_event('delete', resource, id))

    handler.__name__ = handler.__qualname__ = f'delete_{slug}'
    return delete(f'{path}/{{id:str}}')(handler)


# ---------------------------------------------------------------------------
# Special endpoint factories
# ---------------------------------------------------------------------------

def _make_ho_meta(model, prefix: str):
    @get(f'{prefix}/ho_meta')
    async def ho_meta() -> dict:
        from half_orm.null import NULL
        from half_orm_gen.backend.ho_api.models import HoApiModels
        meta = model.ho_meta()
        api = HoApiModels(model)
        label_rows = await api.field()(label_order=('is not', NULL)).ho_aselect(
            'schema_name', 'table_name', 'column_name', 'label_order',
        )
        by_resource: dict[str, list] = {}
        for row in label_rows:
            by_resource.setdefault(f"{row['schema_name']}/{row['table_name']}", []).append(row)
        for resource, rows in by_resource.items():
            if resource in meta:
                rows.sort(key=lambda r: r['label_order'])
                meta[resource]['label_fields'] = [r['column_name'] for r in rows]
        return meta
    return ho_meta


def _make_ho_roles(roles_holder: list, prefix: str):
    """roles_holder[0] is the roles list, populated at startup."""
    @get(f'{prefix}/ho_roles')
    async def ho_roles() -> list:
        return roles_holder[0]
    return ho_roles


def _make_ho_access(access_map_holder: list, parent_map_holder: list, model, prefix: str):
    """access_map_holder[0] is the access map, populated at startup."""
    @get(f'{prefix}/ho_access')
    async def ho_access(request: Request) -> dict:
        roles = _get_roles(request)
        return _filter_access_for_roles(access_map_holder[0], roles, parent_map_holder[0])
    return ho_access


def _make_auth_peers(model, prefix: str):
    """Return trusted peers (id, name, url) + whether local DB auth is enabled.

    Public, unauthenticated — used by the login page to render "sign in
    via ..." buttons and decide whether to show the email/password form
    (HO_LOCAL_AUTH=none means a federation-only peer, no local sign-in).
    `id` is the peer's own HO_PEER_ID (uuid) — the actual delegation lookup
    key (see ho_api/federation.py); `name` is display-only.
    See ho_api/federation.py and planning/identite_federee.md.
    """
    @get(f'{prefix}/auth/peers')
    async def auth_peers() -> dict:
        import os
        from half_orm_gen.backend.ho_api.identity_models import HoIdentityModels
        identity = HoIdentityModels(model)
        rows = await identity.peer()(trusted=True).ho_aselect('id', 'name', 'url')
        return {
            'peers': rows,
            'local_auth_enabled': os.environ.get('HO_LOCAL_AUTH', 'db') != 'none',
        }
    return auth_peers


def _make_ho_setup(model, prefix: str):
    """Return {has_admin: bool} — used by the frontend to detect first-run state."""
    @get(f'{prefix}/ho_setup')
    async def ho_setup() -> dict:
        from half_orm_gen.backend.ho_api.models import HoApiModels
        api = HoApiModels(model)
        rows = await api.user_role()(role_name='admin').ho_aselect('user_id')
        return {'has_admin': bool(rows)}
    return ho_setup


def _make_ho_search(
    prefix: str,
    classes_by_res: dict,
    crud_access_by_res: dict,
    api_excluded_by_res: dict,
    all_fields_by_res: dict,
    parent_map_holder: list,
):
    @get(f'{prefix}/ho_search')
    async def ho_search(
        request: Request,
        q: Optional[str] = None,
        limit: Optional[int] = 5,
        resource: Optional[str] = None,
    ) -> dict:
        from half_orm_gen.backend.ho_api.registry import _FILTER_REGISTRY
        if not q or not q.strip():
            return {}
        term = q.strip()
        roles = _expand_roles(_get_roles(request), parent_map_holder[0])
        result: dict = {}

        candidates = {resource: classes_by_res[resource]} if resource and resource in classes_by_res else classes_by_res
        for res_key, cls in candidates.items():
            schema_name, table_name = res_key.split('/')
            crud_access = crud_access_by_res.get(res_key, {})
            api_excluded = api_excluded_by_res.get(res_key, [])

            searchable_cols: list[str] = []
            for role in roles:
                rv = crud_access.get('GET', {}).get(role, {})
                if isinstance(rv, dict):
                    for f in rv.get('searchable', []):
                        if f not in searchable_cols:
                            searchable_cols.append(f)
            if not searchable_cols:
                continue

            pk_names = list(getattr(cls(), '_ho_pkey', {}).keys())
            authorized = _effective_out_fields(
                crud_access, 'GET', roles, api_excluded,
                all_fields_by_res.get(res_key, []), pk_names or None,
            )
            if not authorized:
                continue

            role_filter = _get_role_filter(crud_access, 'GET', roles)

            inst = None
            for field in searchable_cols:
                part = cls(**{field: ('ilike', '%' + term + '%')})
                getattr(part, field).unaccent = True
                if inst is None:
                    inst = part
                else:
                    inst |= part

            if role_filter:
                inst &= cls(**role_filter)

            for filter_name in _get_active_filters(crud_access, 'GET', roles):
                fn = _FILTER_REGISTRY.get((schema_name, table_name, filter_name))
                if fn:
                    inst &= fn(cls(), request) or cls()

            rows = await inst.ho_aselect(*authorized, limit=limit)
            data = list(rows)

            if data:
                result[res_key] = {
                    'data': data,
                    'searchable_fields': searchable_cols,
                    'has_more': len(data) == limit,
                }

        return result

    return ho_search


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
  /ho_meta   : full schema (fields, PKs, FKs) for all resources
  /ho_roles  : exposes all declared roles (no authentication)
  /ho_access : exposes the full access map filtered by role
  _get_roles : bearer token used directly as a role name
               (no signature verification)
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
    route_handlers: list | None = None,
    **litestar_kwargs,
) -> Litestar:
    """
    Build a Litestar application dynamically from a halfORM model.

    Registers routes for all relations at build time. Access configuration
    (roles, field restrictions) is loaded from "half_orm_meta.api" at startup.
    """
    prefix = f'/v{api_version}' if api_version is not None else ''

    # Mutable containers populated at startup — handlers close over these refs
    crud_access_by_res: dict[str, dict]  = {}
    api_excluded_by_res: dict[str, list] = {}
    all_fields_by_res: dict[str, list]   = {}
    access_map_holder: list  = [{}]   # access_map_holder[0]  = actual map
    parent_map_holder: list  = [{}]   # parent_map_holder[0]  = {role: parent_name}
    roles_holder: list       = [[]]   # roles_holder[0]       = sorted roles list

    ws_rmap: dict = {}
    classes_by_res: dict[str, type] = {}
    relation_handlers: list = []

    for cls, _kind in model.classes():
        try:
            mod = importlib.import_module(cls.__module__)
        except ModuleNotFoundError:
            mod = None

        # API_EXCLUDED_FIELDS stays in Python modules
        api_excluded: list[str] = getattr(mod, 'API_EXCLUDED_FIELDS', []) if mod else []

        inst    = cls()
        schema  = inst._t_fqrn[1]
        table   = inst._t_fqrn[2]
        resource = f'{schema}/{table}'
        path     = f'{prefix}/{resource}'
        pk_info  = _pk_info(cls)

        api_excluded_by_res[resource] = api_excluded
        classes_by_res[resource] = cls

        if pk_info and len(pk_info) == 1:
            ws_rmap[resource] = (cls, pk_info[0][0])

        relation_handlers.append(
            _make_list_handler(path, cls, resource, crud_access_by_res, api_excluded_by_res, all_fields_by_res, parent_map_holder, [p[0] for p in pk_info] if pk_info else None)
        )
        if pk_info:
            relation_handlers.append(
                _make_get_handler(path, cls, resource, crud_access_by_res, api_excluded_by_res, all_fields_by_res, pk_info, parent_map_holder)
            )
            relation_handlers.append(
                _make_post_handler(path, cls, resource, crud_access_by_res, api_excluded_by_res, all_fields_by_res, pk_info[0][0], parent_map_holder)
            )
            relation_handlers.append(
                _make_put_handler(path, cls, resource, crud_access_by_res, api_excluded_by_res, all_fields_by_res, pk_info, parent_map_holder)
            )
            relation_handlers.append(
                _make_delete_handler(path, cls, resource, crud_access_by_res, api_excluded_by_res, pk_info, ws_rmap, parent_map_holder)
            )

    from half_orm_gen.backend.litestar.v2.ho_admin import make_ho_admin_handlers
    from half_orm_gen.backend.litestar.v2.identity_admin import make_identity_admin_handlers
    special_handlers = [
        _make_ho_meta(model, prefix),
        _make_ho_roles(roles_holder, prefix),
        _make_ho_access(access_map_holder, parent_map_holder, model, prefix),
        _make_ho_setup(model, prefix),
        _make_auth_peers(model, prefix),
        _make_ho_search(prefix, classes_by_res, crud_access_by_res, api_excluded_by_res, all_fields_by_res, parent_map_holder),
        _make_ws_handler(prefix),
        *make_ho_admin_handlers(model, prefix, crud_access_by_res, api_excluded_by_res, access_map_holder, parent_map_holder),
        *make_identity_admin_handlers(model, prefix),
    ]

    logging_config = LoggingConfig(
        loggers={'app': {'level': 'ERROR', 'handlers': ['queue_listener']}}
    )

    async def _reload_all_access() -> None:
        """Re-read CRUD_ACCESS / access map / role hierarchy from the DB for every
        resource. Shared by startup and the SIGHUP-triggered live reload below —
        the only way to pick up config written directly to "half_orm_meta.api"
        (e.g. a fixture replay) without going through /ho_admin/* (which already
        calls the single-resource equivalent, _reload_resource_access, itself).
        """
        access_map: dict = {}

        for cls, _kind in model.classes():
            inst     = cls()
            schema   = inst._t_fqrn[1]
            table    = inst._t_fqrn[2]
            resource = f'{schema}/{table}'
            api_excluded = api_excluded_by_res.get(resource, [])

            crud_access = await load_crud_access(model, schema, table) or {}
            crud_access_by_res[resource] = crud_access

            sfqrn = inst._t_fqrn
            all_field_names = list(model._fields_metadata(sfqrn).keys())
            all_fields_by_res[resource] = [f for f in all_field_names if f not in api_excluded]

            resource_pk_info = _pk_info(cls)
            pk_names = [p[0] for p in resource_pk_info] if resource_pk_info else None
            access_entry = _build_access_entry(crud_access, api_excluded, all_field_names, pk_names)

            if access_entry:
                access_map[resource] = access_entry

        access_map_holder[0] = access_map
        parent_map_holder[0] = await load_role_parents(model)
        roles_holder[0] = sorted(k for k in parent_map_holder[0] if k != 'anonymous')

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

        await ensure_system_roles(model)
        await reconcile_catalog(model)

        from half_orm_gen.backend.ho_api.registry import discover_and_register
        await discover_and_register(model, model.classes())

        await _reload_all_access()

        # SIGHUP: conventional "reload config" signal (nginx, postgres, ...).
        # Lets an operator (or `make demo-blog-access-load`) apply config written
        # directly to "half_orm_meta.api" — e.g. a fixture replay — without
        # restarting the process. Requires a single-worker deployment (the signal
        # only reaches the process it's sent to).
        def _on_sighup() -> None:
            async def _do_reload() -> None:
                await _reload_all_access()
                await _manager.broadcast(_ws_event('access_reload'))
                print('Reloaded CRUD_ACCESS/roles from DB (SIGHUP)', file=sys.stderr, flush=True)
            asyncio.ensure_future(_do_reload())

        try:
            asyncio.get_running_loop().add_signal_handler(signal.SIGHUP, _on_sighup)
        except (NotImplementedError, RuntimeError):
            pass  # e.g. Windows, or no running loop (shouldn't happen in on_startup)

    all_handlers = special_handlers + relation_handlers
    if route_handlers and prefix:
        all_handlers += [Router(path=prefix, route_handlers=route_handlers)]
    elif route_handlers:
        all_handlers += route_handlers

    return Litestar(
        route_handlers=all_handlers,
        middleware=middleware or [],
        logging_config=logging_config,
        on_startup=[_startup],
        **litestar_kwargs,
    )
