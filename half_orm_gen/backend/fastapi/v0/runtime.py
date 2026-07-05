"""
Dynamic FastAPI application builder from a halfORM model.

Replaces code-generated ho_api/app.py route handlers with runtime-constructed
closures. Routes are registered at server startup by reading CRUD_ACCESS from
relation modules.
"""
import importlib
import re
import sys
from contextlib import asynccontextmanager
from typing import Optional, List, Any

from fastapi import FastAPI, APIRouter, HTTPException, Request
from fastapi.websockets import WebSocket, WebSocketDisconnect

from half_orm_gen.backend.crud_helpers import (
    _COMPOSITE_PK_PATTERN, _py_type_str,
    _get_roles, _get_role_filter,
    _effective_out_fields, _effective_in_fields,
    _resolved_out, _resolved_in,
    _parse_q, _build_access_entry, _filter_access_for_roles,
    _ws_broadcast_cascade,
    _ws_event,
)
from half_orm_gen.backend.ho_api.loader import ensure_system_roles


# ---------------------------------------------------------------------------
# Shared WebSocket manager
# ---------------------------------------------------------------------------

class _ConnectionManager:
    def __init__(self):
        self._sockets: set = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._sockets.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._sockets.discard(ws)

    async def broadcast(self, message: dict) -> None:
        import json as _json
        dead = set()
        for s in set(self._sockets):
            try:
                await s.send_text(_json.dumps(message, default=str))
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
# PK introspection  (_py_type_str imported from crud_helpers)
# ---------------------------------------------------------------------------

def _pk_info(cls) -> list[tuple[str, str]]:
    """Return [(field_name, py_type_str), ...] for PK columns."""
    pkey = getattr(cls(), '_ho_pkey', {})
    return [(name, _py_type_str(obj.py_type)) for name, obj in pkey.items()]


# ---------------------------------------------------------------------------
# Pydantic body model factory
# ---------------------------------------------------------------------------

def _make_body_model(model, sfqrn: tuple, pk_names: list[str], api_excluded: list[str], name: str):
    """Build a Pydantic model for POST/PUT bodies from halfORM field metadata."""
    from pydantic import create_model, BaseModel
    field_defs: dict = {}
    for fname, fobj in model._fields_metadata(sfqrn).items():
        if fname in pk_names or fname in api_excluded:
            continue
        py_type = getattr(fobj, 'py_type', None) or Any
        field_defs[fname] = (Optional[py_type], None)
    if not field_defs:
        return BaseModel
    return create_model(name, **field_defs)


# ---------------------------------------------------------------------------
# Route handler factories
# ---------------------------------------------------------------------------

def _make_list_handler(cls, crud_access: dict, api_excluded: list, all_field_names: list, resource: str):
    slug = resource.replace('/', '_')
    all_fn = [f for f in all_field_names if f not in api_excluded]

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
        col_filters: dict = {
            k[7:]: v
            for k, v in request.query_params.items()
            if k.startswith('ho_col_') and k[7:] not in api_excluded
        }
        role_filter = _get_role_filter(crud_access, 'GET', roles)
        authorized = _effective_out_fields(crud_access, 'GET', roles, api_excluded, all_fn)
        if not authorized:
            raise HTTPException(status_code=403)
        projection = [f for f in fields if f in authorized] if fields else authorized
        inst = cls(**{**filter_kwargs, **col_filters, **role_filter})
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
    return handler


def _make_get_handler(cls, crud_access: dict, api_excluded: list, all_field_names: list,
                      pk_info: list[tuple[str, str]], resource: str):
    pk_names = [p[0] for p in pk_info]
    is_simple = len(pk_names) == 1
    pk_name = pk_info[0][0]
    slug = resource.replace('/', '_')
    all_fn = [f for f in all_field_names if f not in api_excluded]

    async def handler(request: Request, id: str) -> dict:
        roles = _get_roles(request)
        role_filter = _get_role_filter(crud_access, 'GET', roles)
        authorized = _effective_out_fields(crud_access, 'GET', roles, api_excluded, all_fn)
        if not authorized:
            raise HTTPException(status_code=403)
        pk_filter = {pk_name: id} if is_simple else _parse_composite_pk(id, pk_names)
        rows = await cls(**{**pk_filter, **role_filter}).ho_aselect(*authorized)
        if not rows:
            raise HTTPException(status_code=404)
        return rows[0]

    handler.__name__ = handler.__qualname__ = f'get_{slug}'
    return handler


def _make_post_handler(cls, crud_access: dict, api_excluded: list, all_field_names: list,
                       resource: str, pk_name: str, body_model):
    slug = resource.replace('/', '_')
    all_fn = [f for f in all_field_names if f not in api_excluded]

    async def handler(request: Request, data: body_model) -> dict:
        roles = _get_roles(request)
        in_fields = _effective_in_fields(crud_access, 'POST', roles, api_excluded, all_fn)
        if not in_fields:
            raise HTTPException(status_code=403)
        payload = {
            k: v for k, v in data.model_dump(exclude_none=True).items()
            if k in in_fields
        }
        result = await cls(**payload).ho_ainsert()
        pk_val = result.get(pk_name, '') if result else ''
        await _manager.broadcast(_ws_event('create', resource, pk_val))
        return result

    handler.__name__ = handler.__qualname__ = f'create_{slug}'
    return handler


def _make_put_handler(cls, crud_access: dict, api_excluded: list, all_field_names: list,
                      pk_info: list[tuple[str, str]], resource: str, body_model):
    pk_names = [p[0] for p in pk_info]
    is_simple = len(pk_names) == 1
    pk_name = pk_info[0][0]
    slug = resource.replace('/', '_')
    all_fn = [f for f in all_field_names if f not in api_excluded]

    async def handler(request: Request, id: str, data: body_model) -> dict:
        roles = _get_roles(request)
        in_fields = _effective_in_fields(crud_access, 'PUT', roles, api_excluded, all_fn)
        authorized = _effective_out_fields(crud_access, 'PUT', roles, api_excluded, all_fn)
        if not in_fields:
            raise HTTPException(status_code=403)
        payload = {
            k: v for k, v in data.model_dump(exclude_none=True).items()
            if k in in_fields
        }
        pk_filter = {pk_name: id} if is_simple else _parse_composite_pk(id, pk_names)
        cols = authorized if authorized else ['*']
        result = await cls(**pk_filter).ho_aupdate(*cols, **payload)
        if not result:
            raise HTTPException(status_code=404)
        await _manager.broadcast(_ws_event('update', resource, id))
        return result[0] if authorized else {'ok': True, 'id': str(id)}

    handler.__name__ = handler.__qualname__ = f'update_{slug}'
    return handler


def _make_delete_handler(cls, crud_access: dict, api_excluded: list,
                         pk_info: list[tuple[str, str]], resource: str, ws_rmap: dict):
    pk_names = [p[0] for p in pk_info]
    is_simple = len(pk_names) == 1
    pk_name = pk_info[0][0]
    slug = resource.replace('/', '_')

    async def handler(request: Request, id: str) -> None:
        pk_filter = {pk_name: id} if is_simple else _parse_composite_pk(id, pk_names)
        inst = cls(**pk_filter)
        await _ws_broadcast_cascade(inst, resource, id, ws_rmap, _manager.broadcast)
        result = await inst.ho_adelete('*')
        if not result:
            raise HTTPException(status_code=404)
        await _manager.broadcast(_ws_event('delete', resource, id))

    handler.__name__ = handler.__qualname__ = f'delete_{slug}'
    return handler


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
    extra_routers: list | None = None,
    **fastapi_kwargs,
) -> FastAPI:
    """
    Build a FastAPI application dynamically from a halfORM model.

    Reads CRUD_ACCESS from relation modules at startup and registers
    routes programmatically — no code generation needed.
    """
    prefix = f'/v{api_version}' if api_version is not None else ''

    router = APIRouter()
    access_map: dict = {}
    roles_set: set[str] = set()
    ws_rmap: dict = {}

    for cls, _kind in model.classes():
        try:
            mod = importlib.import_module(cls.__module__)
        except ModuleNotFoundError:
            mod = None
        crud_access = getattr(mod, 'CRUD_ACCESS', None) if mod else None
        no_crud = crud_access is None
        if not crud_access:
            crud_access = {'GET': {}, 'POST': {}, 'PUT': {}, 'DELETE': {}}

        api_excluded: list[str] = getattr(mod, 'API_EXCLUDED_FIELDS', []) if mod else []

        inst = cls()
        schema = inst._t_fqrn[1]
        table  = inst._t_fqrn[2]
        resource = f'{schema}/{table}'
        path     = f'{prefix}/{resource}'
        pk_info  = _pk_info(cls)

        sfqrn = inst._t_fqrn
        all_field_names = list(model._fields_metadata(sfqrn).keys())
        pk_names = [p[0] for p in pk_info]
        slug = resource.replace('/', '_')
        body_model = _make_body_model(model, sfqrn, pk_names, api_excluded, f'Body_{slug}')

        for verb_roles in crud_access.values():
            if isinstance(verb_roles, dict):
                roles_set.update(verb_roles.keys())

        access_entry = _build_access_entry(crud_access, api_excluded, all_field_names)

        if access_entry:
            access_map[resource] = access_entry

        if pk_info and len(pk_info) == 1:
            ws_rmap[resource] = (cls, pk_info[0][0])

        dev_fallback = no_crud and not model._production_mode
        has_get    = bool(crud_access.get('GET'))    or dev_fallback
        has_post   = bool(crud_access.get('POST'))   or dev_fallback
        has_put    = bool(crud_access.get('PUT'))    or dev_fallback
        has_delete = bool(crud_access.get('DELETE')) or dev_fallback

        if has_get:
            router.add_api_route(
                path,
                _make_list_handler(cls, crud_access, api_excluded, all_field_names, resource),
                methods=['GET'],
            )
            if pk_info:
                router.add_api_route(
                    f'{path}/{{id}}',
                    _make_get_handler(cls, crud_access, api_excluded, all_field_names, pk_info, resource),
                    methods=['GET'],
                )

        if has_post and pk_info:
            router.add_api_route(
                path,
                _make_post_handler(cls, crud_access, api_excluded, all_field_names, resource, pk_info[0][0], body_model),
                methods=['POST'],
            )

        if has_put and pk_info:
            router.add_api_route(
                f'{path}/{{id}}',
                _make_put_handler(cls, crud_access, api_excluded, all_field_names, pk_info, resource, body_model),
                methods=['PUT'],
            )

        if has_delete and pk_info:
            router.add_api_route(
                f'{path}/{{id}}',
                _make_delete_handler(cls, crud_access, api_excluded, pk_info, resource, ws_rmap),
                methods=['DELETE'],
            )

    roles_list = sorted(roles_set - {'anonymous'})

    # Special routes
    @router.get(f'{prefix}/ho_meta')
    async def ho_meta() -> dict:
        return model.ho_meta()

    @router.get(f'{prefix}/ho_roles')
    async def ho_roles() -> list:
        return roles_list

    @router.get(f'{prefix}/ho_access')
    async def ho_access(request: Request) -> dict:
        roles = _get_roles(request)
        return _filter_access_for_roles(access_map, roles)

    @router.websocket(f'{prefix}/ws')
    async def ws_handler(ws: WebSocket) -> None:
        await _manager.connect(ws)
        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            _manager.disconnect(ws)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
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
        yield

    app = FastAPI(lifespan=lifespan, **fastapi_kwargs)
    app.include_router(router)

    for extra_router in (extra_routers or []):
        app.include_router(extra_router)

    return app
