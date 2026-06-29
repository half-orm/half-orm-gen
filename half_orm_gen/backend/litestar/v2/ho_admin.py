"""
Admin endpoints for managing CRUD access rights via "half_orm_meta.api" tables.

All endpoints require an active role of 'admin'.
After each mutating operation the in-memory crud_access_by_res and
access_map_holder are refreshed so that /ho_access reflects the change
immediately, without a server restart.
"""
import uuid
from typing import Any

from litestar import Request, get, post, put, delete
from litestar.exceptions import HTTPException

from half_orm_gen.backend.crud_helpers import _get_roles
from half_orm_gen.backend.ho_api.loader import load_crud_access, load_role_parents
from half_orm_gen.backend.ho_api.models import HoApiModels
from half_orm_gen.backend.ho_api.registry import _ROLE_REGISTRY
from half_orm_gen.backend.litestar.v2.runtime import _manager


def _check_admin(request: Request) -> list[str]:
    roles = _get_roles(request)
    if 'admin' not in roles:
        raise HTTPException(
            status_code=403,
            detail=f'Admin access required (current roles: {roles})',
        )
    return roles


async def _reload_resource_access(
    model, resource: str,
    crud_access_by_res: dict, api_excluded_by_res: dict, access_map_holder: list,
) -> None:
    """Reload one resource's access from DB and update the in-memory dicts."""
    from half_orm_gen.backend.litestar.v2.runtime import _build_access_entry

    schema, table = resource.split('/', 1)
    crud_access = await load_crud_access(model, schema, table) or {}
    crud_access_by_res[resource] = crud_access

    api_excluded = api_excluded_by_res.get(resource, [])
    rel_cls = model.get_relation_class(f'{schema}.{table}')
    rel_inst = rel_cls()
    sfqrn = rel_inst._t_fqrn
    all_field_names = list(model._fields_metadata(sfqrn).keys())
    pk_fields = list(getattr(rel_inst, '_ho_pkey', {}).keys()) or None

    access_entry = _build_access_entry(crud_access, api_excluded, all_field_names, pk_fields)

    access_map = dict(access_map_holder[0])
    if access_entry:
        access_map[resource] = access_entry
    else:
        access_map.pop(resource, None)
    access_map_holder[0] = access_map


async def _resource_for_access(api: HoApiModels, access_id: uuid.UUID) -> str | None:
    rows = await api.access()(id=access_id).ho_aselect('schema_name', 'table_name')
    if not rows:
        return None
    return f"{rows[0]['schema_name']}/{rows[0]['table_name']}"


def make_ho_admin_handlers(
    model, prefix: str,
    crud_access_by_res: dict, api_excluded_by_res: dict,
    access_map_holder: list, parent_map_holder: list,
) -> list:
    api = HoApiModels(model)

    async def _reload(resource: str) -> None:
        await _reload_resource_access(
            model, resource, crud_access_by_res, api_excluded_by_res, access_map_holder
        )
        await _manager.broadcast({'event': 'access_reload', 'resource': resource})

    async def _reload_parent_map() -> None:
        parent_map_holder[0] = await load_role_parents(model)
        await _manager.broadcast({'event': 'access_reload'})

    @get(f'{prefix}/ho_admin/roles')
    async def ho_admin_roles(request: Request) -> list:
        _check_admin(request)
        rows = await api.role()().ho_aselect()
        dynamic_role_names = {name for (_, _, name) in _ROLE_REGISTRY}
        return [
            {
                'name':        r['name'],
                'deletable':   r['deletable'],
                'parent_name': r['parent_name'],
                'kind': (
                    'dynamic' if r['name'] in dynamic_role_names
                    else 'system' if not r['deletable']
                    else 'user'
                ),
            }
            for r in rows
        ]

    @post(f'{prefix}/ho_admin/roles')
    async def ho_admin_create_role(request: Request, data: dict[str, Any]) -> dict:
        _check_admin(request)
        name        = data.get('name', '').strip()
        parent_name = data.get('parent_name', 'connected')
        if not name:
            raise HTTPException(status_code=400, detail='name required')
        await api.role()(name=name, deletable=True, parent_name=parent_name).ho_ainsert()
        await _reload_parent_map()
        return {'name': name, 'parent_name': parent_name}

    @delete(f'{prefix}/ho_admin/roles/{{name:str}}')
    async def ho_admin_delete_role(request: Request, name: str) -> None:
        _check_admin(request)
        try:
            result = await api.role()(name=name).ho_adelete('*')
        except Exception as exc:
            if 'ForeignKeyViolation' in type(exc).__name__ or 'foreign key' in str(exc).lower():
                raise HTTPException(status_code=409, detail=f'Role "{name}" still has child roles')
            raise
        if not result:
            raise HTTPException(status_code=404, detail=f'Role "{name}" not found')
        await _reload_parent_map()

    @put(f'{prefix}/ho_admin/roles/{{name:str}}/parent')
    async def ho_admin_set_role_parent(request: Request, name: str, data: dict[str, Any]) -> dict:
        _check_admin(request)
        parent_name = data.get('parent_name')
        result = await api.role()(name=name).ho_aupdate(parent_name=parent_name)
        if not result:
            raise HTTPException(status_code=404, detail=f'Role "{name}" not found')
        await _reload_parent_map()
        return {'name': name, 'parent_name': parent_name}

    @get(f'{prefix}/ho_admin/catalog')
    async def ho_admin_catalog(request: Request) -> dict:
        _check_admin(request)
        routes = await api.route()().ho_aselect()
        relations: dict[tuple, list] = {}
        for row in routes:
            key = (row['schema_name'], row['table_name'])
            relations.setdefault(key, []).append(row['verb'])

        result = {}
        for (schema, table), verbs in relations.items():
            resource_key = f'{schema}/{table}'
            field_rows = await api.field()(
                schema_name=schema, table_name=table, deprecated=False
            ).ho_aselect('column_name')
            fields = [r['column_name'] for r in field_rows]

            rel_cls = model.get_relation_class(f'{schema}.{table}')
            rel_inst = rel_cls()
            pk_fields = list(rel_inst._ho_pkey.keys())
            ho_fields = getattr(rel_inst, '_ho_fields', {})
            fields_with_defaults = [
                f for f, obj in ho_fields.items()
                if getattr(obj, 'has_default_value', None) is not None
            ]

            dynamic_roles = [name for (s, t, name) in _ROLE_REGISTRY if s == schema and t == table]

            filter_rows = await api.filter()(schema_name=schema, table_name=table).ho_aselect()
            filters = [{'id': str(r['id']), 'name': r['name']} for r in filter_rows]

            access: dict = {}
            for verb in verbs:
                acc_rows = await api.access()(
                    schema_name=schema, table_name=table, verb=verb
                ).ho_aselect()
                verb_entry: dict = {}
                for acc in acc_rows:
                    out_rows = await api.field_access_out()(access_id=acc['id']).ho_aselect('field_name')
                    in_rows  = await api.field_access_in()(access_id=acc['id']).ho_aselect('field_name')
                    af_rows  = await api.access_filter()(access_id=acc['id']).ho_aselect('filter_id')
                    verb_entry[acc['role_name']] = {
                        'id':             str(acc['id']),
                        'out':            [r['field_name'] for r in out_rows],
                        'in':             [r['field_name'] for r in in_rows],
                        'active_filters': [str(r['filter_id']) for r in af_rows],
                    }
                if verb_entry:
                    access[verb] = verb_entry

            result[resource_key] = {
                'fields':               fields,
                'pk_fields':            pk_fields,
                'fields_with_defaults': fields_with_defaults,
                'dynamic_roles':        dynamic_roles,
                'filters':              filters,
                'access':               access,
            }
        return result

    @post(f'{prefix}/ho_admin/access')
    async def ho_admin_create_access(request: Request, data: dict[str, Any]) -> dict:
        _check_admin(request)
        role_name = data.get('role_name')
        schema    = data.get('schema_name')
        table     = data.get('table_name')
        verb      = data.get('verb')
        if not all([role_name, schema, table, verb]):
            raise HTTPException(status_code=400, detail='role_name, schema_name, table_name, verb required')
        result = await api.access()(
            role_name=role_name, schema_name=schema, table_name=table, verb=verb,
        ).ho_ainsert()
        await _reload(f'{schema}/{table}')
        return {'id': str(result['id'])}

    @delete(f'{prefix}/ho_admin/access/{{id:str}}')
    async def ho_admin_delete_access(request: Request, id: str) -> None:
        _check_admin(request)
        uid = uuid.UUID(id)
        resource = await _resource_for_access(api, uid)
        result = await api.access()(id=uid).ho_adelete('*')
        if not result:
            raise HTTPException(status_code=404)
        if resource:
            await _reload(resource)

    @post(f'{prefix}/ho_admin/field_access_out')
    async def ho_admin_add_field_out(request: Request, data: dict[str, Any]) -> dict:
        _check_admin(request)
        access_id  = data.get('access_id')
        field_name = data.get('field_name')
        if not access_id or not field_name:
            raise HTTPException(status_code=400, detail='access_id and field_name required')
        uid = uuid.UUID(access_id)
        await api.field_access_out()(access_id=uid, field_name=field_name).ho_ainsert()
        resource = await _resource_for_access(api, uid)
        if resource:
            await _reload(resource)
        return {'access_id': access_id, 'field_name': field_name}

    @post(f'{prefix}/ho_admin/field_access_out/batch')
    async def ho_admin_add_fields_out_batch(request: Request, data: dict[str, Any]) -> dict:
        _check_admin(request)
        access_id   = data.get('access_id')
        field_names = data.get('field_names', [])
        if not access_id or not field_names:
            raise HTTPException(status_code=400, detail='access_id and field_names required')
        uid = uuid.UUID(access_id)
        for field_name in field_names:
            await api.field_access_out()(access_id=uid, field_name=field_name).ho_ainsert()
        resource = await _resource_for_access(api, uid)
        if resource:
            await _reload(resource)
        return {'access_id': access_id, 'field_names': field_names}

    @delete(f'{prefix}/ho_admin/field_access_out/{{access_id:str}}/{{field_name:str}}')
    async def ho_admin_remove_field_out(request: Request, access_id: str, field_name: str) -> None:
        _check_admin(request)
        uid = uuid.UUID(access_id)
        resource = await _resource_for_access(api, uid)
        result = await api.field_access_out()(access_id=uid, field_name=field_name).ho_adelete('*')
        if not result:
            raise HTTPException(status_code=404)
        if resource:
            await _reload(resource)

    @post(f'{prefix}/ho_admin/field_access_in')
    async def ho_admin_add_field_in(request: Request, data: dict[str, Any]) -> dict:
        _check_admin(request)
        access_id  = data.get('access_id')
        field_name = data.get('field_name')
        if not access_id or not field_name:
            raise HTTPException(status_code=400, detail='access_id and field_name required')
        uid = uuid.UUID(access_id)
        await api.field_access_in()(access_id=uid, field_name=field_name).ho_ainsert()
        resource = await _resource_for_access(api, uid)
        if resource:
            await _reload(resource)
        return {'access_id': access_id, 'field_name': field_name}

    @post(f'{prefix}/ho_admin/field_access_in/batch')
    async def ho_admin_add_fields_in_batch(request: Request, data: dict[str, Any]) -> dict:
        _check_admin(request)
        access_id   = data.get('access_id')
        field_names = data.get('field_names', [])
        if not access_id or not field_names:
            raise HTTPException(status_code=400, detail='access_id and field_names required')
        uid = uuid.UUID(access_id)
        for field_name in field_names:
            await api.field_access_in()(access_id=uid, field_name=field_name).ho_ainsert()
        resource = await _resource_for_access(api, uid)
        if resource:
            await _reload(resource)
        return {'access_id': access_id, 'field_names': field_names}

    @delete(f'{prefix}/ho_admin/field_access_in/{{access_id:str}}/{{field_name:str}}')
    async def ho_admin_remove_field_in(request: Request, access_id: str, field_name: str) -> None:
        _check_admin(request)
        uid = uuid.UUID(access_id)
        resource = await _resource_for_access(api, uid)
        result = await api.field_access_in()(access_id=uid, field_name=field_name).ho_adelete('*')
        if not result:
            raise HTTPException(status_code=404)
        if resource:
            await _reload(resource)

    @post(f'{prefix}/ho_admin/access_filter')
    async def ho_admin_add_access_filter(request: Request, data: dict[str, Any]) -> dict:
        _check_admin(request)
        access_id = data.get('access_id')
        filter_id = data.get('filter_id')
        if not access_id or not filter_id:
            raise HTTPException(status_code=400, detail='access_id and filter_id required')
        uid = uuid.UUID(access_id)
        await api.access_filter()(access_id=uid, filter_id=uuid.UUID(filter_id)).ho_ainsert()
        resource = await _resource_for_access(api, uid)
        if resource:
            await _reload(resource)
        return {'access_id': access_id, 'filter_id': filter_id}

    @delete(f'{prefix}/ho_admin/access_filter/{{access_id:str}}/{{filter_id:str}}')
    async def ho_admin_remove_access_filter(request: Request, access_id: str, filter_id: str) -> None:
        _check_admin(request)
        uid = uuid.UUID(access_id)
        resource = await _resource_for_access(api, uid)
        result = await api.access_filter()(
            access_id=uid, filter_id=uuid.UUID(filter_id)
        ).ho_adelete('*')
        if not result:
            raise HTTPException(status_code=404)
        if resource:
            await _reload(resource)

    return [
        ho_admin_roles,
        ho_admin_create_role,
        ho_admin_delete_role,
        ho_admin_set_role_parent,
        ho_admin_catalog,
        ho_admin_create_access,
        ho_admin_delete_access,
        ho_admin_add_field_out,
        ho_admin_add_fields_out_batch,
        ho_admin_remove_field_out,
        ho_admin_add_field_in,
        ho_admin_add_fields_in_batch,
        ho_admin_remove_field_in,
        ho_admin_add_access_filter,
        ho_admin_remove_access_filter,
    ]
