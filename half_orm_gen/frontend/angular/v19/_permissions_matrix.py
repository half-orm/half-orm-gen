from half_orm_gen.backend.crud_routes import _resolved_out, _resolved_in
from ._templates import _tpl


def _build_perm_data(
    crud_access: dict,
    all_field_names: list,
    api_excluded: list,
) -> tuple[str, str]:
    """Return (roles_ts, matrix_ts) TypeScript literals from CRUD_ACCESS.

    matrix_ts encodes VerbAccess objects: { in?: string[] | null, out?: string[] | null }
    null means "all fields"; absent key means "not applicable" (e.g. no 'in' for GET/DELETE).
    """
    verbs = ('GET', 'POST', 'PUT', 'DELETE')
    all_roles: set[str] = set()
    for verb in verbs:
        all_roles.update(crud_access.get(verb, {}).keys())
    roles_sorted = sorted(all_roles)

    def _fields_ts(field_list) -> str:
        if field_list is None or not isinstance(field_list, (list, tuple, set)):
            return 'null'
        filtered = [f for f in field_list if f not in api_excluded and f in all_field_names]
        return '[' + ', '.join(f"'{f}'" for f in filtered) + ']'

    rows = []
    for role in roles_sorted:
        verb_entries = []
        for v in verbs:
            if role not in crud_access.get(v, {}):
                continue
            parts = []
            if v in ('POST', 'PUT'):
                in_val = _resolved_in(crud_access, v, role)
                parts.append(f'in: {_fields_ts(in_val)}')
            if v != 'DELETE':
                out_val = _resolved_out(crud_access, v, role)
                parts.append(f'out: {_fields_ts(out_val)}')
            verb_str = '{ ' + ', '.join(parts) + ' }' if parts else '{}'
            verb_entries.append(f'{v}: {verb_str}')
        if verb_entries:
            rows.append(f"    '{role}': {{ {', '.join(verb_entries)} }}")

    roles_ts = '[' + ', '.join(f"'{r}'" for r in roles_sorted) + ']'
    matrix_ts = ('{\n' + ',\n'.join(rows) + '\n  }') if rows else '{}'
    return roles_ts, matrix_ts


def _permissions_fields_component_ts() -> str:
    return _tpl('permissions_matrix/permissions-fields.component.ts').substitute()


def _permissions_matrix_component_ts() -> str:
    return _tpl('permissions_matrix/permissions-matrix.component.ts').substitute()
