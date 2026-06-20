"""
Auto-CRUD route generation from CRUD_ACCESS + halfORM introspection.

For each relation module that defines CRUD_ACCESS, generates Litestar
route handlers for the verbs declared, skipping any verb already covered
by an @api_* decorated method.
"""

import importlib
import json
import pprint
from typing import Iterable, Tuple, Type

from half_orm.relation import Relation

from half_orm_gen import templates as T
from half_orm_gen.api_routes import _annotation_str


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
    return _annotation_str(py_type)


def _path_type_str(py_type) -> str:
    return _LITESTAR_PATH_TYPE_MAP.get(_py_type_str(py_type), 'str')


def _instance(relation):
    return relation()


def _pk_info(relation) -> list[tuple[str, str, str]]:
    """Return [(field_name, litestar_path_type, py_type_str), ...] for all PK columns.
    Returns [] for relations with no PK (views, etc.).
    """
    pkey = getattr(_instance(relation), '_ho_pkey', {})
    return [(name, _path_type_str(obj.py_type), _py_type_str(obj.py_type))
            for name, obj in pkey.items()]


def _simple_pk(relation) -> Tuple[str, str, str] | None:
    """Return (pk_field_name, litestar_path_type, py_type_str) for single-column PKs only."""
    cols = _pk_info(relation)
    return cols[0] if len(cols) == 1 else None


def _filter_params_str(all_fields: dict) -> Tuple[str, str]:
    """Return (filter_params_block, filter_dict_str) for query-param filters."""
    lines = []
    dict_items = []
    for fname, fobj in all_fields.items():
        type_str = _py_type_str(fobj.py_type)
        lines.append(f'    {fname}: Optional[{type_str}] = None,\n')
        dict_items.append(f"'{fname}': {fname}")
    return ''.join(lines), ', '.join(dict_items)


# ---------------------------------------------------------------------------
# CRUD_ACCESS parsing helpers
# ---------------------------------------------------------------------------

def _resolved_out(crud_access: dict, verb: str, role: str):
    """Return the 'out' field list (or None) for role/verb, resolving GET inheritance."""
    rv = crud_access.get(verb, {}).get(role)
    if verb in ('GET', 'DELETE'):
        return rv  # sugar form: value IS out (or None = all)
    if not isinstance(rv, dict):
        return None
    if 'out' in rv:
        return rv['out']
    # inherit from GET
    get_rv = crud_access.get('GET', {}).get(role)
    return get_rv if not isinstance(get_rv, dict) else get_rv.get('out')


def _resolved_in(crud_access: dict, verb: str, role: str):
    """Return the 'in' field list (or None = all fields) for role/verb."""
    rv = crud_access.get(verb, {}).get(role)
    if not isinstance(rv, dict):
        return None
    return rv.get('in')


def _gen_out_fields(crud_access: dict, verb: str, api_excluded: list, all_field_names: list) -> list:
    """Union of out fields across all roles for a verb (generation-time, for TypedDicts)."""
    collected = []
    for role in crud_access.get(verb, {}):
        out = _resolved_out(crud_access, verb, role)
        if out is None:
            return [f for f in all_field_names if f not in api_excluded]
        collected.extend(out)
    seen = set()
    result = []
    for f in collected:
        if f not in seen and f not in api_excluded and f in all_field_names:
            seen.add(f)
            result.append(f)
    return result


def _gen_in_fields(crud_access: dict, verb: str, pk_field: str,
                   api_excluded: list, all_field_names: list,
                   pk_has_default: bool = True) -> list:
    """Union of in fields across all roles for a verb, minus excluded fields.
    PK is excluded only when pk_has_default is True (DB generates it).
    For PUT the PK is always excluded (it comes from the URL path).
    """
    exclude_pk = pk_field if pk_has_default else None
    collected = []
    for role in crud_access.get(verb, {}):
        in_val = _resolved_in(crud_access, verb, role)
        if in_val is None:
            return [f for f in all_field_names if f != exclude_pk and f not in api_excluded]
        collected.extend(in_val)
    seen = set()
    result = []
    for f in collected:
        if f not in seen and f not in api_excluded and f != exclude_pk and f in all_field_names:
            seen.add(f)
            result.append(f)
    return result


def _typedict_block(class_name: str, field_names: list, all_fields: dict) -> str:
    """Return a TypedDict class definition string."""
    lines = [f'class {class_name}(TypedDict, total=False):']
    valid = [(f, all_fields[f]) for f in field_names if f in all_fields]
    if not valid:
        lines.append('    pass')
    else:
        for fname, fobj in valid:
            lines.append(f'    {fname}: Optional[{_py_type_str(fobj.py_type)}]')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# /access endpoint payload builder
# ---------------------------------------------------------------------------

def _build_access_entry(
    crud_access: dict,
    api_excluded: list,
    all_names: list,
    covered: set,
    module_str: str,
) -> dict:
    """Build the access map entry for one relation (used by GET /access)."""
    entry = {}
    for verb in ('GET', 'POST', 'PUT', 'DELETE'):
        if (module_str, verb) in covered:
            continue
        roles = crud_access.get(verb)
        if not roles:
            continue
        verb_entry = {}
        for role, rv in roles.items():
            if verb == 'GET':
                out = rv if not isinstance(rv, dict) else rv.get('out')
                verb_entry[role] = {
                    'out': (
                        [f for f in all_names if f not in api_excluded]
                        if out is None else
                        [f for f in out if f not in api_excluded]
                    )
                }
            elif verb == 'DELETE':
                verb_entry[role] = 'allowed'
            else:  # POST / PUT
                in_val = _resolved_in(crud_access, verb, role)
                out    = _resolved_out(crud_access, verb, role)
                verb_entry[role] = {
                    'in': (
                        [f for f in all_names if f not in api_excluded]
                        if in_val is None else
                        [f for f in in_val if f not in api_excluded]
                    ),
                    'out': (
                        [f for f in all_names if f not in api_excluded]
                        if out is None else
                        [f for f in out if f not in api_excluded]
                    ),
                }
        if verb_entry:
            entry[verb] = verb_entry
    return entry


# ---------------------------------------------------------------------------
# OpenAPI description
# ---------------------------------------------------------------------------

def _access_description(crud_access: dict, verb: str) -> str:
    """Format CRUD_ACCESS role/field info for a verb as an OpenAPI description."""
    roles = crud_access.get(verb, {})
    if not roles:
        return ""
    lines = ["**Access**"]
    for role, rv in roles.items():
        if verb == 'GET':
            if rv is None:
                lines.append(f"- {role}: all fields")
            else:
                lines.append(f"- {role}: {', '.join(rv)}")
        elif verb == 'DELETE':
            lines.append(f"- {role}: allowed")
        else:
            # POST / PUT — {"in": ..., "out": ...}
            parts = []
            in_val = rv.get('in') if isinstance(rv, dict) else None
            parts.append("in=all" if in_val is None else f"in=[{', '.join(in_val)}]")
            out = _resolved_out(crud_access, verb, role)
            parts.append("out=all" if out is None else f"out=[{', '.join(out)}]")
            lines.append(f"- {role}: {', '.join(parts)}")
    return "\\n".join(lines)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate_crud_access(crud_access: dict, module_str: str) -> None:
    valid_verbs = {'GET', 'POST', 'PUT', 'PATCH', 'DELETE'}
    for verb, roles in crud_access.items():
        if verb not in valid_verbs:
            print(f'  WARNING {module_str}.CRUD_ACCESS: unknown verb "{verb}"')
            continue
        if verb == 'DELETE':
            for role, rv in roles.items():
                if isinstance(rv, dict):
                    print(f'  WARNING {module_str}.CRUD_ACCESS["DELETE"]["{role}"]: '
                          f'dict form has no effect on DELETE (no request body) — use None')


# ---------------------------------------------------------------------------
# Main generation
# ---------------------------------------------------------------------------

def generate_crud_routes(
    classes: Iterable[Tuple[Type[Relation], str]],
    api_version,
    covered: set,
    templates=None,
) -> Tuple[list, list]:
    """Generate auto-CRUD blocks for all relations that define CRUD_ACCESS.

    Skips verbs already covered by @api_* (present in *covered* set).
    Returns (blocks, route_handler_names).
    """
    if templates is None:
        templates = T

    decl_blocks: list[str] = []   # imports + typedicts
    handler_blocks: list[str] = [] # route handlers
    route_handlers: list[str] = []
    access_map: dict = {}
    ho_dev_map: dict = {}
    roles: set[str] = {'ho_dev'}
    crud_resource_map: list[tuple] = []  # (resource, module_alias, class_name, pk_field)

    version_prefix = f'/v{api_version}' if api_version is not None else ''

    for relation, _relation_type in classes:
        module_str   = relation.__module__
        schema       = '.'.join(module_str.split('.')[:-1])
        module_name  = module_str.split('.')[-1]
        module_alias = module_str.replace('.', '_')

        try:
            mod = importlib.import_module(module_str)
        except ImportError as exc:
            print(f'  WARNING: cannot import {module_str}: {exc}')
            continue

        crud_access = getattr(mod, 'CRUD_ACCESS', None)
        if not crud_access:
            crud_access = {'GET': {}, 'POST': {}, 'PUT': {}, 'DELETE': {}}

        _validate_crud_access(crud_access, module_str)

        for verb_roles in crud_access.values():
            if isinstance(verb_roles, dict):
                roles.update(verb_roles.keys())

        api_excluded = getattr(mod, 'API_EXCLUDED_FIELDS', [])
        kind         = getattr(relation, '_ho_kind', 'Table')
        is_table     = kind == 'Table'
        schema_name  = relation._t_fqrn[1]
        table_name   = relation._t_fqrn[2]
        base_path    = f'{version_prefix}/{schema_name}/{table_name}'
        resource     = f'{schema_name}/{table_name}'
        handler_prefix = f'_crud_{module_alias}'
        pk_cols      = _pk_info(relation)
        pk_info      = pk_cols  # truthy iff non-empty

        if len(pk_cols) == 1:
            pk_field, pk_path_type, pk_py_type = pk_cols[0]
            pk_instance_filter  = f'{pk_field}=id'
            pk_broadcast_expr   = f'result.get("{pk_field}")'
        elif len(pk_cols) > 1:
            pk_field  = pk_cols[0][0]   # first field; used in WS cascade map
            pk_path_type = 'str'
            pk_py_type   = 'str'
            _pk_names = [f for f, _, _ in pk_cols]
            pk_instance_filter = f"**dict(zip({_pk_names!r}, id.split('::')))"
            pk_broadcast_expr  = f"'::'.join(str(result.get(f, '')) for f in {_pk_names!r})"
        else:
            pk_field = pk_path_type = pk_py_type = pk_instance_filter = pk_broadcast_expr = None

        instance     = _instance(relation)
        all_fields   = getattr(instance, '_ho_fields', {})
        all_names    = list(all_fields.keys())

        decl_blocks.append(templates.CRUD_MODULE_IMPORT.format(
            schema=schema,
            module_name=module_name,
            module_alias=module_alias,
        ))

        # Out TypedDict / Pydantic model (driven by GET, used for all return types)
        out_class  = f'_Out_{module_alias}'
        out_names  = _gen_out_fields(crud_access, 'GET', api_excluded, all_names)
        if not out_names:
            out_names = [f for f in all_names if f not in api_excluded]
        decl_blocks.append('\n' + templates.typedict_block(out_class, out_names, all_fields) + '\n')

        filter_params, filter_dict = _filter_params_str(all_fields)
        get_desc = _access_description(crud_access, 'GET')

        # GET list
        if (module_str, 'GET') not in covered and 'GET' in crud_access:
            handler_name = f'{handler_prefix}_list'
            handler_blocks.append(templates.CRUD_GET_LIST.format(
                path=base_path,
                handler_name=handler_name,
                filter_params=filter_params,
                filter_dict=filter_dict,
                module_alias=module_alias,
                class_name=relation.__name__,
                out_typedict=out_class,
                access_description=get_desc,
            ))
            route_handlers.append(handler_name)

        # GET /{pk}
        if pk_info and (module_str, 'GET') not in covered and 'GET' in crud_access:
            handler_name = f'{handler_prefix}_get'
            handler_blocks.append(templates.CRUD_GET_ONE.format(
                path=base_path,
                handler_name=handler_prefix,
                pk_instance_filter=pk_instance_filter,
                pk_path_type=pk_path_type,
                pk_py_type=pk_py_type,
                module_alias=module_alias,
                class_name=relation.__name__,
                out_typedict=out_class,
                access_description=get_desc,
            ))
            route_handlers.append(handler_name)

        # Write verbs — tables only
        if is_table and pk_info:
            pk_has_default = bool(
                pk_field and all_fields.get(pk_field) and
                all_fields[pk_field].has_default_value is not None
            )
            if (module_str, 'POST') not in covered and 'POST' in crud_access:
                post_in_class = f'_In_{module_alias}_post'
                post_in_names = _gen_in_fields(crud_access, 'POST', pk_field, api_excluded, all_names,
                                               pk_has_default)
                if not post_in_names:
                    post_in_names = [f for f in all_names
                                     if (f != pk_field or not pk_has_default) and f not in api_excluded]
                decl_blocks.append('\n' + templates.typedict_block(post_in_class, post_in_names, all_fields) + '\n')
                handler_name = f'{handler_prefix}_create'
                handler_blocks.append(templates.CRUD_POST.format(
                    path=base_path,
                    handler_name=handler_prefix,
                    module_alias=module_alias,
                    class_name=relation.__name__,
                    in_typedict=post_in_class,
                    out_typedict=out_class,
                    access_description=_access_description(crud_access, 'POST'),
                    resource=resource,
                    pk_broadcast_expr=pk_broadcast_expr,
                ))
                route_handlers.append(handler_name)

            if (module_str, 'PUT') not in covered and 'PUT' in crud_access:
                put_in_class = f'_In_{module_alias}_put'
                put_in_names = _gen_in_fields(crud_access, 'PUT', pk_field, api_excluded, all_names)
                if not put_in_names:
                    put_in_names = [f for f in all_names if f != pk_field and f not in api_excluded]
                decl_blocks.append('\n' + templates.typedict_block(put_in_class, put_in_names, all_fields) + '\n')
                handler_name = f'{handler_prefix}_update'
                handler_blocks.append(templates.CRUD_PUT.format(
                    path=base_path,
                    handler_name=handler_prefix,
                    pk_instance_filter=pk_instance_filter,
                    pk_path_type=pk_path_type,
                    pk_py_type=pk_py_type,
                    module_alias=module_alias,
                    class_name=relation.__name__,
                    in_typedict=put_in_class,
                    out_typedict=out_class,
                    access_description=_access_description(crud_access, 'PUT'),
                    resource=resource,
                ))
                route_handlers.append(handler_name)

            if (module_str, 'DELETE') not in covered and 'DELETE' in crud_access:
                handler_name = f'{handler_prefix}_delete'
                handler_blocks.append(templates.CRUD_DELETE.format(
                    path=base_path,
                    handler_name=handler_prefix,
                    pk_instance_filter=pk_instance_filter,
                    pk_path_type=pk_path_type,
                    pk_py_type=pk_py_type,
                    module_alias=module_alias,
                    class_name=relation.__name__,
                    access_description=_access_description(crud_access, 'DELETE'),
                    resource=resource,
                ))
                route_handlers.append(handler_name)
                crud_resource_map.append((resource, module_alias, relation.__name__, pk_field))

        # Accumulate access map entry
        map_key = f'{schema_name}/{table_name}'
        entry = _build_access_entry(crud_access, api_excluded, all_names, covered, module_str)
        if entry:
            access_map[map_key] = entry

        # ho_dev_map: full access entry for every generated resource
        out_all = [f for f in all_names if f not in api_excluded]
        ho_dev_entry: dict = {}
        if 'GET' in crud_access and (module_str, 'GET') not in covered:
            ho_dev_entry['GET'] = {'out': out_all}
        if is_table and pk_info:
            _pk_names_set = {f for f, _, _ in pk_cols}
            in_all = [f for f in all_names if f not in api_excluded and f not in _pk_names_set]
            if 'POST' in crud_access and (module_str, 'POST') not in covered:
                ho_dev_entry['POST'] = {'in': in_all, 'out': out_all}
            if 'PUT' in crud_access and (module_str, 'PUT') not in covered:
                ho_dev_entry['PUT'] = {'in': in_all, 'out': out_all}
            if 'DELETE' in crud_access and (module_str, 'DELETE') not in covered:
                ho_dev_entry['DELETE'] = 'allowed'
        if ho_dev_entry:
            ho_dev_map[map_key] = ho_dev_entry

    # Assemble: decl_blocks first, then WS helpers, then route handlers
    blocks = decl_blocks

    # WebSocket push endpoint (defines _manager)
    if hasattr(templates, 'WS_HELPERS'):
        blocks.append(templates.WS_HELPERS.format(version_prefix=version_prefix))
        if getattr(templates, 'FRAMEWORK', 'litestar') == 'litestar':
            route_handlers.append('_ws_handler')

    # Cascade broadcast helper (uses _manager, must come after WS_HELPERS)
    if hasattr(templates, 'WS_CASCADE_HELPER') and crud_resource_map:
        resource_entries = '\n'.join(
            f'    "{res}": ({mod}.{cls}, "{pk}"),'
            for res, mod, cls, pk in crud_resource_map
        )
        blocks.append(templates.WS_CASCADE_HELPER.format(
            resource_entries=resource_entries,
        ))

    blocks.extend(handler_blocks)

    # /ho_roles endpoint — static list of all roles present in CRUD_ACCESS
    if roles:
        blocks.append(
            templates.HO_ROLES_ROUTE.format(
                roles_json=json.dumps(sorted(roles)),
                version_prefix=version_prefix,
            )
        )
        route_handlers.append('_crud_roles_list')

    # /ho_access endpoint — filtered by the caller's authorized_roles
    if ho_dev_map or access_map:
        blocks.append(f'\n_HO_DEV_MAP = {pprint.pformat(ho_dev_map)}\n')
        json_str = json.dumps(access_map, indent=4)
        blocks.append(
            templates.HO_ACCESS_ROUTE.format(
                json_str=json_str,
                version_prefix=version_prefix,
            )
        )
        route_handlers.append('_crud_access_map')

    return blocks, route_handlers
