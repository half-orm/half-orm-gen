"""
Framework-agnostic CRUD helpers used by the Litestar runtime.

Functions here must not import from any specific web framework.
"""
import re
import time
import uuid
import datetime
import decimal
from typing import Any


def _ws_event(event: str, resource: str | None = None, id: Any = None, **extra: Any) -> dict:
    """Build a WebSocket event payload, timestamped in epoch milliseconds (JS Date.now()-compatible)."""
    payload: dict = {'event': event, 'ts': int(time.time() * 1000)}
    if resource is not None:
        payload['resource'] = resource
    if id is not None:
        payload['id'] = str(id)
    payload.update(extra)
    return payload


# ---------------------------------------------------------------------------
# Role / access helpers
# ---------------------------------------------------------------------------

def _get_roles(request: Any) -> list[str]:
    """Extract the role list from a request.

    Priority: request.state.authorized_roles (set by auth middleware) > Bearer token >
    ['anonymous']. The token is used verbatim as a role name — suitable for dev only.
    """
    roles = getattr(request.state, 'authorized_roles', None)
    if roles is not None:
        return roles
    token = request.headers.get('Authorization', '').removeprefix('Bearer ').strip()
    if token:
        return list(dict.fromkeys([token, 'anonymous']))
    return ['anonymous']


def _get_role_filter(crud_access: dict, verb: str, authorized_roles: list[str]) -> dict:
    """Return the merged row-level filter dict for a verb and the caller's roles.

    Combines 'filter' dicts from all matching roles (later roles overwrite earlier
    ones for the same key). Returns {} if no role matches or if no 'filter' key
    is found — meaning no row-level restriction applies.
    """
    role_map = crud_access.get(verb, {})
    combined = {}
    for role in authorized_roles:
        if role not in role_map:
            continue
        rv = role_map[role]
        if rv is None:
            return {}
        if isinstance(rv, dict):
            if 'filter' not in rv:
                return {}
            combined.update(rv['filter'])
    return combined


def _get_active_filters(crud_access: dict, verb: str, roles: list[str]) -> list[str]:
    """Return the named @ho_api_filter filters active for a verb.

    Stops at the most specific role that has its own access entry for this verb
    (mirrors _get_role_filter) — a filter set on an ancestor role (e.g. anonymous)
    does not leak onto descendant roles (e.g. connected, admin) that have their
    own entry, even without an explicit 'filters' key.
    """
    role_map = crud_access.get(verb, {})
    for role in roles:
        if role not in role_map:
            continue
        rv = role_map[role]
        if isinstance(rv, dict):
            return list(rv.get('filters', []))
        return []
    return []


def _effective_out_fields(
    crud_access: dict,
    verb: str,
    authorized_roles: list[str],
    api_excluded: list | None = None,
    all_field_names: list | None = None,
    pk_fields: list | None = None,
) -> list | None:
    """Return the list of fields the caller may read for this verb.

    For non-GET verbs without an explicit 'out', falls back to the GET out
    fields for that role. Returns None when no role matched (→ 403).
    Never returns []. PK fields are always injected into GET results.
    """
    api_excluded = api_excluded or []
    role_map = crud_access.get(verb, {})
    get_map  = crud_access.get('GET', {})
    fields: list[str] = []
    matched = False
    for role in authorized_roles:
        if role not in role_map:
            continue
        matched = True
        rv = role_map[role]
        if isinstance(rv, dict):
            if 'out' in rv:
                out = rv['out'] or []
            else:
                get_rv = get_map.get(role)
                out = get_rv.get('out') or [] if isinstance(get_rv, dict) else []
        else:
            out = []
        fields.extend(f for f in out if f not in api_excluded)
    if not matched:
        return None
    result = list(dict.fromkeys(fields))
    if verb == 'GET' and matched and pk_fields:
        for pk in reversed(pk_fields):
            if pk not in result and pk not in api_excluded:
                result.insert(0, pk)
    return result if result else None


def _effective_in_fields(
    crud_access: dict,
    verb: str,
    authorized_roles: list[str],
    api_excluded: list | None = None,
    all_field_names: list | None = None,
) -> list:
    """Return the list of fields the caller may write for this verb.

    Returns [] when no role matched or no 'in' fields configured → caller raises 403.
    """
    api_excluded = api_excluded or []
    role_map = crud_access.get(verb, {})
    fields: list[str] = []
    for role in authorized_roles:
        if role not in role_map:
            continue
        rv = role_map[role]
        if not isinstance(rv, dict):
            continue
        fields.extend(f for f in (rv.get('in') or []) if f not in api_excluded)
    return list(dict.fromkeys(fields))


def _resolved_out(crud_access: dict, verb: str, role: str) -> list:
    """Resolve the 'out' field list for a single (verb, role) pair.

    For POST/PUT without explicit 'out', falls back to GET out for that role.
    """
    rv = crud_access.get(verb, {}).get(role)
    if not isinstance(rv, dict):
        return []
    if 'out' in rv:
        return rv['out']
    get_rv = crud_access.get('GET', {}).get(role)
    return get_rv.get('out', []) if isinstance(get_rv, dict) else []


def _resolved_in(crud_access: dict, verb: str, role: str) -> list:
    """Resolve the 'in' field list for a single (verb, role) pair."""
    rv = crud_access.get(verb, {}).get(role)
    if not isinstance(rv, dict):
        return []
    return rv.get('in', [])


# ---------------------------------------------------------------------------
# Access-map helpers  (used by /ho_access)
# ---------------------------------------------------------------------------

def _build_access_entry(
    crud_access: dict,
    api_excluded: list,
    all_field_names: list,
    pk_fields: list | None = None,
) -> dict:
    """Build the normalized access entry dict for one resource.

    Expands None/"all fields" shorthands into explicit field lists, applies
    api_excluded, and falls back to GET out fields for PUT/POST out when
    not specified. The result is stored in access_map and served by /ho_access.

    Structure: {verb: {role: {'in': [...], 'out': [...]} | 'allowed'}}
    """
    entry: dict = {}
    for verb in ('GET', 'POST', 'PUT', 'DELETE'):
        roles = crud_access.get(verb)
        if not roles:
            continue
        verb_entry: dict = {}
        for role, rv in roles.items():
            if verb == 'GET':
                rv = roles[role]
                out = rv.get('out', []) if isinstance(rv, dict) else []
                out_fields = [f for f in out if f not in api_excluded]
                if pk_fields:
                    for pk in reversed(pk_fields):
                        if pk not in out_fields and pk not in api_excluded:
                            out_fields.insert(0, pk)
                role_entry: dict = {'out': out_fields}
                searchable = rv.get('searchable', []) if isinstance(rv, dict) else []
                if searchable:
                    role_entry['searchable'] = [f for f in searchable if f not in api_excluded]
                filters = rv.get('filters', []) if isinstance(rv, dict) else []
                if filters:
                    role_entry['filters'] = filters
                verb_entry[role] = role_entry
            elif verb == 'DELETE':
                verb_entry[role] = 'allowed'
            else:
                in_val  = _resolved_in(crud_access, verb, role)
                out_val = _resolved_out(crud_access, verb, role)
                rv_dict = crud_access.get(verb, {}).get(role, {})
                fk_auto = rv_dict.get('fk_auto', {}) if isinstance(rv_dict, dict) else {}
                role_entry: dict = {
                    'in':  [f for f in in_val  if f not in api_excluded],
                    'out': [f for f in out_val if f not in api_excluded],
                }
                if fk_auto:
                    role_entry['fk_auto'] = fk_auto
                verb_entry[role] = role_entry
        if verb_entry:
            entry[verb] = verb_entry
    return entry


def _expand_roles(roles: list[str], parent_map: dict[str, str | None]) -> list[str]:
    """Return roles + all ancestors (child before parent), without duplicates."""
    seen: set[str] = set()
    result: list[str] = []
    for role in roles:
        current: str | None = role
        while current and current not in seen:
            seen.add(current)
            result.append(current)
            current = parent_map.get(current)
    return result


def _filter_access_for_roles(
    access_map: dict,
    authorized_roles: list[str],
    parent_map: dict[str, str | None] | None = None,
) -> dict:
    """Filter the full access map down to what the caller's roles can see.

    Used by the /ho_access endpoint to expose only the relevant subset of
    permissions. For each resource/verb, merges field lists across all matching
    roles (union) — except 'filters', which is a restriction and comes solely
    from the most specific matched role (see _get_active_filters). DELETE is
    collapsed to a boolean. Resources/verbs with no matching role are omitted
    entirely.
    """
    if parent_map:
        authorized_roles = _expand_roles(authorized_roles, parent_map)
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
                    searchable: list = []
                    for v in active.values():
                        out.extend(v.get('out', []))
                        searchable.extend(v.get('searchable', []))
                    get_entry: dict = {'out': list(dict.fromkeys(out))}
                    if searchable:
                        get_entry['searchable'] = list(dict.fromkeys(searchable))
                    # Filters are a restriction, not a grant: use only the most
                    # specific matched role's own entry (first in `active`, since
                    # authorized_roles is child-before-parent) — an ancestor's
                    # filter must not leak onto a descendant role's access.
                    filters = next(iter(active.values())).get('filters', [])
                    if filters:
                        get_entry['filters'] = list(filters)
                    resource_entry[verb] = get_entry
                else:
                    in_f: list = []
                    out_f: list = []
                    fk_auto_merged: dict = {}
                    for v in active.values():
                        in_f.extend(v.get('in', []))
                        out_f.extend(v.get('out', []))
                        fk_auto_merged.update(v.get('fk_auto', {}))
                    verb_result: dict = {
                        'in':  list(dict.fromkeys(in_f)),
                        'out': list(dict.fromkeys(out_f)),
                    }
                    if fk_auto_merged:
                        verb_result['fk_auto'] = fk_auto_merged
                    resource_entry[verb] = verb_result
        if resource_entry:
            result[resource] = resource_entry
    return result


# ---------------------------------------------------------------------------
# Composite PK pattern  (regex shared; _parse_composite_pk raises framework
# HTTPException so it stays in each runtime)
# ---------------------------------------------------------------------------

_COMPOSITE_PK_PATTERN = r'^[a-zA-Z_][a-zA-Z0-9_]*:[^:]+(::[a-zA-Z_][a-zA-Z0-9_]*:[^:]+)*$'


# ---------------------------------------------------------------------------
# PK type helpers
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


def _py_type_str(py_type) -> str:
    """Return a canonical string representation of a Python type for path parameter declarations."""
    return _KNOWN_PY_TYPES.get(py_type, str(py_type))


# ---------------------------------------------------------------------------
# Search-query parser  (reused by list handlers)
# ---------------------------------------------------------------------------

def _parse_q(
    q: str, api_excluded: list[str]
) -> tuple[dict, list[str], list]:
    """Parse the ?q= search string into filter structures for halfORM.

    Accepts comma-separated ``col:value`` pairs. Supports four forms:
      - ``col:text``          → ilike 'text%' (prefix search); col added to search_cols
      - ``col:*text``         → ilike '%text%' (contains search, anywhere in the field);
                                col added to search_cols
      - ``col:>N`` / ``col:<=N``  → single comparison operator (numeric/date range,
                                also usable on text for an alphabetical jump, e.g. ``col:>=M``)
      - ``col:>=A<=B``        → range filter, returned in range_filters

    Returns (filter_kwargs, search_cols, range_filters).
    Fields in api_excluded are silently ignored.
    """
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
            elif val.startswith('*'):
                term = val[1:].strip()
                if term:
                    filter_kwargs[col] = ('ilike', '%' + term + '%')
                    search_cols.append(col)
            else:
                filter_kwargs[col] = ('ilike', val + '%')
                search_cols.append(col)
    return filter_kwargs, search_cols, range_filters


# ---------------------------------------------------------------------------
# WebSocket cascade helper
# broadcast_fn is passed by each framework runtime (e.g. _manager.broadcast)
# ---------------------------------------------------------------------------

async def _ws_broadcast_cascade(
    inst, resource: str, pk_val, ws_rmap: dict,
    broadcast_fn, _seen: set | None = None,
) -> None:
    """Broadcast WebSocket delete events for a resource and its dependents.

    Walks reverse FK relationships recursively, broadcasting a 'delete' event
    for each child row before the parent is deleted. This keeps live UIs in sync
    with cascading deletes at the database level.

    broadcast_fn is injected by the caller (e.g. _manager.broadcast) rather than
    closed over, so this function stays framework-agnostic. _seen prevents cycles.
    """
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
            await _ws_broadcast_cascade(child_cls(**{child_pk: rid}), child_resource, rid, ws_rmap, broadcast_fn, _seen)
            await broadcast_fn(_ws_event('delete', child_resource, rid))
