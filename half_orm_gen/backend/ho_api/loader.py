"""
Load CRUD access configuration from "half_orm_meta.api" tables.

Replaces getattr(mod, 'CRUD_ACCESS', None) in both runtime.py and crud_routes.py.

Cross-table orchestration only — each table's own read/write logic lives on
its own class under half_orm_gen.backend.ho_api.half_orm_meta.
"""


async def load_crud_access(model, schema_name: str, table_name: str) -> dict | None:
    """Reconstruct a CRUD_ACCESS-compatible dict from "half_orm_meta.api" tables.

    Returns None if no routes are defined for this relation.
    """
    Route                 = model.get_relation_class('"half_orm_meta.api".route')
    Access                = model.get_relation_class('"half_orm_meta.api".access')
    FieldAccessOut         = model.get_relation_class('"half_orm_meta.api".field_access_out')
    FieldAccessIn          = model.get_relation_class('"half_orm_meta.api".field_access_in')
    FieldAccessFkAuto      = model.get_relation_class('"half_orm_meta.api".field_access_fk_auto')
    FieldAccessSearchable  = model.get_relation_class('"half_orm_meta.api".field_access_searchable')
    AccessFilter           = model.get_relation_class('"half_orm_meta.api".access_filter')
    Filter                 = model.get_relation_class('"half_orm_meta.api".filter')

    routes = await Route(
        schema_name=schema_name, table_name=table_name, deprecated=False
    ).ho_aselect('verb')
    if not routes:
        return None

    crud_access: dict = {}
    for route_row in routes:
        verb = route_row['verb']
        accesses = await Access.list_for(schema_name, table_name, verb)

        verb_dict: dict = {}
        for acc in accesses:
            role   = acc['role_name']
            acc_id = acc['id']

            if verb == 'DELETE':
                verb_dict[role] = 'allowed'
                continue

            out_list = await FieldAccessOut.list_for(acc_id)
            in_list  = await FieldAccessIn.list_for(acc_id)
            fk_auto  = {r['field_name']: r['resolve_rule'] for r in await FieldAccessFkAuto.list_for(acc_id)}
            srch_rows = await FieldAccessSearchable.list_for(acc_id)

            filter_ids = [r['filter_id'] for r in await AccessFilter.list_for(acc_id)]
            filter_names = [
                name for name in [await Filter.name_for(fid) for fid in filter_ids] if name
            ]

            entry: dict = {}
            # Preserve any searchable already distributed by a parent acc processed earlier
            if verb == 'GET' and 'searchable' in verb_dict.get(role, {}):
                entry['searchable'] = list(verb_dict[role]['searchable'])
            # GET always has 'out'; POST/PUT include 'out' only when explicitly set
            # (absent 'out' triggers fallback to GET out in _resolved_out)
            if verb == 'GET' or out_list:
                entry['out'] = out_list
            if verb in ('POST', 'PUT') and in_list:
                entry['in'] = in_list
            if fk_auto and verb in ('POST', 'PUT'):
                entry['fk_auto'] = fk_auto
            if filter_names:
                entry['filters'] = filter_names
            verb_dict[role] = entry

            # Distribute searchable to the right role entries (role_name=None → own role)
            if verb == 'GET':
                for row in srch_rows:
                    target = row['role_name'] or role
                    verb_dict.setdefault(target, {}).setdefault('searchable', [])
                    if row['field_name'] not in verb_dict[target]['searchable']:
                        verb_dict[target]['searchable'].append(row['field_name'])

        crud_access[verb] = verb_dict

    return crud_access


async def ensure_system_roles(model) -> None:
    """Insert each system role individually if not already present."""
    Role = model.get_relation_class('"half_orm_meta.api".role')
    await Role.ensure_system_roles()


async def load_role_parents(model) -> dict[str, str | None]:
    """Return {role_name: parent_name} for all roles."""
    Role = model.get_relation_class('"half_orm_meta.api".role')
    return await Role.load_parents()


async def load_roles_info(model) -> list[dict]:
    """Return [{name, schema_name, table_name}, ...] for all roles.

    schema_name/table_name are None for a normal (static) role, and set for a
    dynamic one (registered via @ho_api_role on that resource's class — see
    registry.py) — that's what makes it dynamic, and what a client uses to
    know which resource's permissions matrix should offer it as a row.
    """
    Role = model.get_relation_class('"half_orm_meta.api".role')
    return await Role.load_roles_info()


async def reconcile_catalog(ctx) -> None:
    """Sync resource/route/field catalogs with pg_catalog: insert new, flag
    deprecated, unflag restored. Delegates to each table's own class — see
    half_orm_gen.backend.ho_api.half_orm_meta (Resource.sync/Route.sync/
    Field.sync). Callers must have already called half_orm_meta.register_all
    (ctx.meta_model) — reconcile_catalog itself doesn't, so it can run as many
    times as needed (e.g. the SIGHUP live-reload path) without re-registering.

    "half_orm_meta.identity"."user" needs no special-casing here anymore:
    once with_half_orm_meta covers it, ctx.ho_meta() (like ctx.classes())
    yields it like any other relation.
    """
    meta = ctx.ho_meta()
    live_relations = {(v['schema'], v['table']) for v in meta.values()}
    live_fields = {
        (v['schema'], v['table'], f['name'])
        for v in meta.values()
        for f in v.get('fields', [])
    }

    Resource = ctx.meta_model.get_relation_class('"half_orm_meta.api".resource')
    Route    = ctx.meta_model.get_relation_class('"half_orm_meta.api".route')
    Field    = ctx.meta_model.get_relation_class('"half_orm_meta.api".field')

    # Resources first — Route/Field both FK-reference resource(schemaname, relname).
    await Resource.sync(live_relations)
    await Route.sync(live_relations)
    await Field.sync(live_fields)
