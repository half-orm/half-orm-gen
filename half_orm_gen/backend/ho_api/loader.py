"""
Load CRUD access configuration from "half_orm_meta.api" tables.

Replaces getattr(mod, 'CRUD_ACCESS', None) in both runtime.py and crud_routes.py.

Cross-table orchestration only — each table's own read/write logic lives on
its own class under half_orm_gen.backend.ho_api.half_orm_meta.
"""


async def resolve_field_id(model, access_id, field_name: str):
    """Resolve (access_id, field_name) to the matching "half_orm_meta.api".field.id.

    field_access_in/out/searchable/fk_auto all store a field_id (a real FK
    to field, cascading on column drop) but keep field_name in their own
    public .add()/.remove() API, matching every caller across the codebase
    — this is the shared translation, via access's own (schema_name,
    table_name), those four classes' methods call internally.

    Raises ValueError if the access row or the field doesn't exist (a
    bogus/typo'd field_name is now rejected here rather than silently
    accepted, per the field_id migration this replaces).
    """
    Access = model.get_relation_class('"half_orm_meta.api".access')
    Field  = model.get_relation_class('"half_orm_meta.api".field')
    rows = await Access(id=access_id).ho_aselect('schema_name', 'table_name')
    if not rows:
        raise ValueError(f'No access row for id={access_id}')
    schema, table = rows[0]['schema_name'], rows[0]['table_name']
    field_rows = await Field(schema_name=schema, table_name=table, column_name=field_name).ho_aselect('id')
    if not field_rows:
        raise ValueError(f'"{field_name}" is not a column of {schema}.{table}')
    return field_rows[0]['id']


async def resolve_field_names(model, field_ids: list) -> dict:
    """Bulk field_id -> column_name (one query for many ids); {} for empty input."""
    if not field_ids:
        return {}
    Field = model.get_relation_class('"half_orm_meta.api".field')
    rows = await Field(id=('in', tuple(field_ids))).ho_aselect('id', 'column_name')
    return {r['id']: r['column_name'] for r in rows}


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


def _is_pivot(entry: dict) -> bool:
    """True if `entry` (one ctx.ho_meta() value) is a pure many-to-many
    pivot/junction table: its PK is exactly 2 columns, each the sole
    local field of a single-column FK, targeting two DIFFERENT tables.

    Mirrors half_orm_gen.backend.litestar.v2.runtime._pivot_fk_pair, which
    expresses the same 4-part condition against a live Relation class's
    own _ho_fkeys instead of this ho_meta()-shaped dict — keep both in
    sync if this definition ever changes.
    """
    pk_fields = entry.get('pk_fields') or []
    if len(pk_fields) != 2:
        return False
    targets = []
    for pk_field in pk_fields:
        fk = next(
            (fk for fk in entry.get('fk_deps', []) if fk['local_fields'] == [pk_field]),
            None,
        )
        if fk is None:
            return False
        targets.append((fk['remote_schema'], fk['remote_table']))
    return targets[0] != targets[1]


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
    live_relations_with_pivot_flag = {
        (v['schema'], v['table']): _is_pivot(v) for v in meta.values()
    }
    live_fields = {
        (v['schema'], v['table'], f['name'])
        for v in meta.values()
        for f in v.get('fields', [])
    }

    Resource = ctx.meta_model.get_relation_class('"half_orm_meta.api".resource')
    Route    = ctx.meta_model.get_relation_class('"half_orm_meta.api".route')
    Field    = ctx.meta_model.get_relation_class('"half_orm_meta.api".field')

    # Resources first — Route/Field both FK-reference resource(schemaname, relname).
    await Resource.sync(live_relations_with_pivot_flag)
    await Route.sync(live_relations)
    await Field.sync(live_fields)
