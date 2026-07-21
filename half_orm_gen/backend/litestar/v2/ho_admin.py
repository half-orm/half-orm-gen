"""
Admin endpoints for managing CRUD access rights via "half_orm_meta.api" tables.

All endpoints require an active role of 'admin'.
After each mutating operation the in-memory crud_access_by_res and
access_map_holder are refreshed so that /ho_access reflects the change
immediately, without a server restart.

Thin HTTP layer only — each table's own read/write logic lives on its own
class under half_orm_gen.backend.ho_api.half_orm_meta (Role, Access,
FieldAccessIn/Out/FkAuto/Searchable, Filter, AccessFilter, Field).
"""
import uuid
from typing import Any

from litestar import Request, get, post, put, delete
from litestar.exceptions import HTTPException

from half_orm_gen.backend.crud_helpers import _get_roles, _expand_roles, _filter_access_for_roles, _ws_event
from half_orm_gen.backend.ho_api.loader import load_crud_access, load_role_parents
from half_orm_gen.backend.ho_api.registry import _ROLE_REGISTRY
from half_orm_gen.backend.litestar.v2.runtime import _manager


def _is_server_generated_default(dv: str) -> bool:
    """True only for function-based or current_* defaults — not simple scalars like 'false' or '0'."""
    dv = dv.lower().strip()
    return dv.startswith('current') or '(' in dv


def _check_admin(request: Request) -> list[str]:
    roles = _get_roles(request)
    if 'admin' not in roles:
        raise HTTPException(
            status_code=403,
            detail=f'Admin access required (current roles: {roles})',
        )
    return roles


async def _reload_resource_access(
    ctx, resource: str,
    crud_access_by_res: dict, api_excluded_by_res: dict, access_map_holder: list,
) -> None:
    """Reload one resource's access from DB and update the in-memory dicts."""
    from half_orm_gen.backend.litestar.v2.runtime import _build_access_entry

    schema, table = resource.split('/', 1)
    crud_access = await load_crud_access(ctx.meta_model, schema, table) or {}
    crud_access_by_res[resource] = crud_access

    api_excluded = api_excluded_by_res.get(resource, [])
    rel_cls = ctx.model_for(schema).get_relation_class(f'{schema}.{table}')
    rel_inst = rel_cls()
    sfqrn = rel_inst._t_fqrn
    all_field_names = list(rel_inst._ho_model._fields_metadata(sfqrn).keys())
    pk_fields = list(getattr(rel_inst, '_ho_pkey', {}).keys()) or None

    access_entry = _build_access_entry(crud_access, api_excluded, all_field_names, pk_fields)

    access_map = dict(access_map_holder[0])
    if access_entry:
        access_map[resource] = access_entry
    else:
        access_map.pop(resource, None)
    access_map_holder[0] = access_map


def make_ho_admin_handlers(
    ctx, prefix: str,
    crud_access_by_res: dict, api_excluded_by_res: dict,
    access_map_holder: list, parent_map_holder: list,
) -> list:
    model = ctx.meta_model
    Role                  = model.get_relation_class('"half_orm_meta.api".role')
    Route                 = model.get_relation_class('"half_orm_meta.api".route')
    Access                = model.get_relation_class('"half_orm_meta.api".access')
    Field                 = model.get_relation_class('"half_orm_meta.api".field')
    FieldAccessOut         = model.get_relation_class('"half_orm_meta.api".field_access_out')
    FieldAccessIn          = model.get_relation_class('"half_orm_meta.api".field_access_in')
    FieldAccessFkAuto      = model.get_relation_class('"half_orm_meta.api".field_access_fk_auto')
    FieldAccessSearchable  = model.get_relation_class('"half_orm_meta.api".field_access_searchable')
    Filter                 = model.get_relation_class('"half_orm_meta.api".filter')
    AccessFilter           = model.get_relation_class('"half_orm_meta.api".access_filter')

    async def _reload(resource: str) -> None:
        await _reload_resource_access(
            ctx, resource, crud_access_by_res, api_excluded_by_res, access_map_holder
        )
        await _manager.broadcast(_ws_event('access_reload', resource))

    async def _reload_parent_map() -> None:
        parent_map_holder[0] = await load_role_parents(model)
        await _manager.broadcast(_ws_event('access_reload'))

    @get(f'{prefix}/ho_admin/roles')
    async def ho_admin_roles(request: Request) -> list:
        _check_admin(request)
        dynamic_role_names = {name for (_, _, name) in _ROLE_REGISTRY}
        return await Role.list_all(dynamic_role_names)

    @post(f'{prefix}/ho_admin/roles')
    async def ho_admin_create_role(request: Request, data: dict[str, Any]) -> dict:
        _check_admin(request)
        name        = data.get('name', '').strip()
        parent_name = data.get('parent_name', 'connected')
        if not name:
            raise HTTPException(status_code=400, detail='name required')
        await Role.create(name, parent_name)
        await _reload_parent_map()
        return {'name': name, 'parent_name': parent_name}

    @delete(f'{prefix}/ho_admin/roles/{{name:str}}')
    async def ho_admin_delete_role(request: Request, name: str) -> None:
        _check_admin(request)
        try:
            deleted = await Role.delete(name)
        except Exception as exc:
            if 'ForeignKeyViolation' in type(exc).__name__ or 'foreign key' in str(exc).lower():
                raise HTTPException(status_code=409, detail=f'Role "{name}" still has child roles')
            raise
        if not deleted:
            raise HTTPException(status_code=404, detail=f'Role "{name}" not found')
        await _reload_parent_map()

    @put(f'{prefix}/ho_admin/roles/{{name:str}}/parent')
    async def ho_admin_set_role_parent(request: Request, name: str, data: dict[str, Any]) -> dict:
        _check_admin(request)
        parent_name = data.get('parent_name')
        ok = await Role.set_parent(name, parent_name)
        if not ok:
            raise HTTPException(status_code=404, detail=f'Role "{name}" not found')
        await _reload_parent_map()
        return {'name': name, 'parent_name': parent_name}

    @get(f'{prefix}/ho_admin/catalog')
    async def ho_admin_catalog(request: Request) -> dict:
        _check_admin(request)
        routes = await Route.list_all()
        relations: dict[tuple, list] = {}
        for row in routes:
            key = (row['schema_name'], row['table_name'])
            relations.setdefault(key, []).append(row['verb'])

        result = {}
        for (schema, table), verbs in relations.items():
            resource_key = f'{schema}/{table}'
            field_rows = await Field.list_for(schema, table)
            fields = [r['column_name'] for r in field_rows]
            label_fields = [
                r['column_name'] for r in sorted(
                    (r for r in field_rows if r['label_order'] is not None),
                    key=lambda r: r['label_order'],
                )
            ]

            rel_cls = ctx.model_for(schema).get_relation_class(f'{schema}.{table}')
            rel_inst = rel_cls()
            pk_fields = list(rel_inst._ho_pkey.keys())
            ho_fields = getattr(rel_inst, '_ho_fields', {})
            fields_with_defaults = [
                f for f, obj in ho_fields.items()
                if getattr(obj, 'has_default_value', None) is not None
                and _is_server_generated_default(obj.has_default_value)
            ]

            fk_deps = []
            for fk in getattr(rel_inst, '_ho_fkeys', {}).values():
                if fk.is_reverse:
                    continue
                fqtn = fk.remote['fqtn']
                fk_deps.append({
                    'fields':        list(fk.names),
                    'target':        f'{fqtn[0]}/{fqtn[1]}',
                    'target_fields': list(fk.fk_names),
                })

            dynamic_roles = [name for (s, t, name) in _ROLE_REGISTRY if s == schema and t == table]
            filters = await Filter.list_for(schema, table)

            access: dict = {}
            pmap = parent_map_holder[0]

            def _ancestors(role: str) -> list[str]:
                result, cur = [], pmap.get(role)
                while cur:
                    result.append(cur)
                    cur = pmap.get(cur)
                return result

            for verb in verbs:
                acc_rows = await Access.list_for(schema, table, verb)
                verb_entry: dict = {}
                for acc in acc_rows:
                    role             = acc['role_name']
                    out_list         = await FieldAccessOut.list_for(acc['id'])
                    in_list          = await FieldAccessIn.list_for(acc['id'])
                    af_rows          = await AccessFilter.list_for(acc['id'])
                    fk_auto_rows     = await FieldAccessFkAuto.list_for(acc['id'])
                    searchable_rows  = await FieldAccessSearchable.list_for(acc['id'])

                    # Preserve searchable already distributed to this role by a parent acc
                    pre_searchable = list(verb_entry.get(role, {}).get('searchable', []))
                    entry = {
                        'id':             str(acc['id']),
                        'out':            out_list,
                        'in':             in_list,
                        'fk_auto':        {r['field_name']: r['resolve_rule'] for r in fk_auto_rows},
                        'active_filters': [str(r['filter_id']) for r in af_rows],
                        'searchable':     pre_searchable,
                    }
                    verb_entry[role] = entry

                    # Distribute searchable to the right role entries (role_name=None → own role)
                    if verb == 'GET':
                        for row in searchable_rows:
                            target = row['role_name'] or role
                            if target == role:
                                if row['field_name'] not in entry['searchable']:
                                    entry['searchable'].append(row['field_name'])
                            else:
                                if target not in verb_entry:
                                    verb_entry[target] = {
                                        'id': str(acc['id']),
                                        'out': [], 'in': [], 'fk_auto': {},
                                        'active_filters': [], 'searchable': [],
                                        '_searchable_only': True,
                                    }
                                if row['field_name'] not in verb_entry[target]['searchable']:
                                    verb_entry[target]['searchable'].append(row['field_name'])
                for role, entry in verb_entry.items():
                    direct_out = set(entry['out'])
                    direct_in  = set(entry['in'])
                    inh_out: list[str] = []
                    inh_in:  list[str] = []
                    for anc in _ancestors(role):
                        if anc in verb_entry:
                            for f in verb_entry[anc]['out']:
                                if f not in direct_out and f not in inh_out:
                                    inh_out.append(f)
                            for f in verb_entry[anc]['in']:
                                if f not in direct_in and f not in inh_in:
                                    inh_in.append(f)
                    entry['inherited_out'] = inh_out
                    entry['inherited_in']  = inh_in
                if verb_entry:
                    access[verb] = verb_entry

            result[resource_key] = {
                'fields':               fields,
                'label_fields':         label_fields,
                'pk_fields':            pk_fields,
                'fields_with_defaults': fields_with_defaults,
                'fk_deps':              fk_deps,
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
        access_id, pk_fields = await Access.create(role_name, schema, table, verb, parent_map_holder[0], ctx.model_for(schema))
        await _reload(f'{schema}/{table}')
        return {'id': str(access_id), 'pk_fields': pk_fields}

    @delete(f'{prefix}/ho_admin/access/{{id:str}}')
    async def ho_admin_delete_access(request: Request, id: str) -> None:
        _check_admin(request)
        uid = uuid.UUID(id)
        resource = await Access.delete(uid)
        if not resource:
            raise HTTPException(status_code=404)
        await _reload(resource)

    @post(f'{prefix}/ho_admin/field_access_out')
    async def ho_admin_add_field_out(request: Request, data: dict[str, Any]) -> dict:
        _check_admin(request)
        access_id  = data.get('access_id')
        field_name = data.get('field_name')
        if not access_id or not field_name:
            raise HTTPException(status_code=400, detail='access_id and field_name required')
        uid = uuid.UUID(access_id)
        await FieldAccessOut.add(uid, field_name)
        resource = await Access.resource_for(uid)
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
        await FieldAccessOut.add_batch(uid, field_names)
        resource = await Access.resource_for(uid)
        if resource:
            await _reload(resource)
        return {'access_id': access_id, 'field_names': field_names}

    @delete(f'{prefix}/ho_admin/field_access_out/{{access_id:str}}/{{field_name:str}}')
    async def ho_admin_remove_field_out(request: Request, access_id: str, field_name: str) -> None:
        _check_admin(request)
        uid = uuid.UUID(access_id)
        resource = await Access.resource_for(uid)
        removed = await FieldAccessOut.remove(uid, field_name)
        if not removed:
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
        await FieldAccessIn.add(uid, field_name)
        resource = await Access.resource_for(uid)
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
        await FieldAccessIn.add_batch(uid, field_names)
        resource = await Access.resource_for(uid)
        if resource:
            await _reload(resource)
        return {'access_id': access_id, 'field_names': field_names}

    @delete(f'{prefix}/ho_admin/field_access_in/{{access_id:str}}/{{field_name:str}}')
    async def ho_admin_remove_field_in(request: Request, access_id: str, field_name: str) -> None:
        _check_admin(request)
        uid = uuid.UUID(access_id)
        resource = await Access.resource_for(uid)
        removed = await FieldAccessIn.remove(uid, field_name)
        if not removed:
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
        await AccessFilter.add(uid, uuid.UUID(filter_id))
        resource = await Access.resource_for(uid)
        if resource:
            await _reload(resource)
        return {'access_id': access_id, 'filter_id': filter_id}

    @delete(f'{prefix}/ho_admin/access_filter/{{access_id:str}}/{{filter_id:str}}')
    async def ho_admin_remove_access_filter(request: Request, access_id: str, filter_id: str) -> None:
        _check_admin(request)
        uid = uuid.UUID(access_id)
        resource = await Access.resource_for(uid)
        removed = await AccessFilter.remove(uid, uuid.UUID(filter_id))
        if not removed:
            raise HTTPException(status_code=404)
        if resource:
            await _reload(resource)

    @post(f'{prefix}/ho_admin/field_access_fk_auto')
    async def ho_admin_set_fk_auto(request: Request, data: dict[str, Any]) -> dict:
        _check_admin(request)
        access_id    = data.get('access_id')
        field_name   = data.get('field_name')
        resolve_rule = data.get('resolve_rule')
        if not access_id or not field_name or not resolve_rule:
            raise HTTPException(status_code=400, detail='access_id, field_name and resolve_rule required')
        uid = uuid.UUID(access_id)
        try:
            await FieldAccessFkAuto.set(uid, field_name, resolve_rule)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        resource = await Access.resource_for(uid)
        if resource:
            await _reload(resource)
        return {'access_id': access_id, 'field_name': field_name, 'resolve_rule': resolve_rule}

    @delete(f'{prefix}/ho_admin/field_access_fk_auto/{{access_id:str}}/{{field_name:str}}')
    async def ho_admin_remove_fk_auto(request: Request, access_id: str, field_name: str) -> None:
        _check_admin(request)
        uid = uuid.UUID(access_id)
        resource = await Access.resource_for(uid)
        removed = await FieldAccessFkAuto.remove(uid, field_name)
        if not removed:
            raise HTTPException(status_code=404)
        if resource:
            await _reload(resource)

    @post(f'{prefix}/ho_admin/field_access_searchable')
    async def ho_admin_add_searchable(request: Request, data: dict[str, Any]) -> dict:
        _check_admin(request)
        access_id  = data.get('access_id')
        field_name = data.get('field_name')
        role_name  = data.get('role_name')  # None = same role as access owner
        if not access_id or not field_name:
            raise HTTPException(status_code=400, detail='access_id and field_name required')
        uid = uuid.UUID(access_id)
        await FieldAccessSearchable.add(uid, field_name, role_name)
        resource = await Access.resource_for(uid)
        if resource:
            await _reload(resource)
        return {'access_id': access_id, 'field_name': field_name, 'role_name': role_name}

    @delete(f'{prefix}/ho_admin/field_access_searchable/{{access_id:str}}/{{field_name:str}}')
    async def ho_admin_remove_searchable(request: Request, access_id: str, field_name: str) -> None:
        _check_admin(request)
        uid = uuid.UUID(access_id)
        resource = await Access.resource_for(uid)
        removed = await FieldAccessSearchable.remove(uid, field_name)
        if not removed:
            raise HTTPException(status_code=404)
        if resource:
            await _reload(resource)

    @post(f'{prefix}/ho_admin/field_label')
    async def ho_admin_set_field_label(request: Request, data: dict[str, Any]) -> dict:
        """Mark a field as (part of) a resource's display label.

        Resource-level, not per-role — unlike fk_auto/searchable, this isn't
        scoped to an access row. Concatenation order across multiple label
        fields is `label_order` (0, 1, 2...).

        Invariant: a label field must be searchable for every role with GET
        access to this resource (the FK select combobox and global search
        both filter on label fields via `q=`) — auto-granted here rather
        than left for the admin to remember.
        """
        _check_admin(request)
        schema      = data.get('schema_name')
        table       = data.get('table_name')
        field_name  = data.get('field_name')
        label_order = data.get('label_order')
        if not all([schema, table, field_name]) or label_order is None:
            raise HTTPException(
                status_code=400,
                detail='schema_name, table_name, field_name, label_order required',
            )
        await Field.set_label(schema, table, field_name, label_order)

        acc_rows = await Access.list_for(schema, table, 'GET')
        for acc in acc_rows:
            existing = await FieldAccessSearchable.list_for(acc['id'])
            if field_name not in {r['field_name'] for r in existing}:
                await FieldAccessSearchable.add(acc['id'], field_name)

        resource = f'{schema}/{table}'
        await _reload(resource)
        return {'schema_name': schema, 'table_name': table, 'field_name': field_name, 'label_order': label_order}

    @delete(f'{prefix}/ho_admin/field_label/{{schema_name:str}}/{{table_name:str}}/{{field_name:str}}')
    async def ho_admin_unset_field_label(
        request: Request, schema_name: str, table_name: str, field_name: str,
    ) -> None:
        _check_admin(request)
        await Field.unset_label(schema_name, table_name, field_name)
        await _reload(f'{schema_name}/{table_name}')

    @get(f'{prefix}/ho_admin/simulate-access')
    async def ho_admin_simulate_access(request: Request, role: str) -> dict:
        _check_admin(request)
        roles = _expand_roles([role], parent_map_holder[0])
        return _filter_access_for_roles(access_map_holder[0], roles, parent_map_holder[0])

    return [
        ho_admin_roles,
        ho_admin_create_role,
        ho_admin_delete_role,
        ho_admin_set_role_parent,
        ho_admin_catalog,
        ho_admin_simulate_access,
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
        ho_admin_set_fk_auto,
        ho_admin_remove_fk_auto,
        ho_admin_add_searchable,
        ho_admin_remove_searchable,
        ho_admin_set_field_label,
        ho_admin_unset_field_label,
    ]
