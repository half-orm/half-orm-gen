"""
Abstract base class for frontend store generators.

Module-level helpers shared across all framework generators.
"""

from abc import ABC, abstractmethod
from pathlib import Path

from half_orm_gen.backend.crud_routes import _py_type_str


# ---------------------------------------------------------------------------
# Name helpers
# ---------------------------------------------------------------------------

def _cname(schema_name: str, table_name: str) -> str:
    """PascalCase — BlogAuthor"""
    schema_name = schema_name.replace('.', '_')
    return ''.join(p.capitalize() for p in f'{schema_name}_{table_name}'.split('_'))


def _rname(schema_name: str, table_name: str) -> str:
    """camelCase — blogAuthor"""
    schema_name = schema_name.replace('.', '_')
    parts = schema_name.split('_') + table_name.split('_')
    return parts[0].lower() + ''.join(p.capitalize() for p in parts[1:])


def _title(schema_name: str, table_name: str) -> str:
    return f'{schema_name}.{table_name}'


# ---------------------------------------------------------------------------
# Field type helpers
# ---------------------------------------------------------------------------

def _field_type_category(field_obj) -> str:
    """Map Python type → validation category: date, datetime, number, or string."""
    py_type = _py_type_str(field_obj.py_type)
    if py_type == 'datetime.date':
        return 'date'
    if py_type == 'datetime.datetime':
        return 'datetime'
    if py_type in ('int', 'float', 'decimal.Decimal'):
        return 'number'
    return 'string'


def _is_bool_field(f: str, all_fields: dict) -> bool:
    return f in all_fields and _py_type_str(all_fields[f].py_type) == 'bool'


def _is_text_field(f: str, all_fields: dict) -> bool:
    return f in all_fields and _py_type_str(all_fields[f].py_type) == 'str'


def _is_textarea_field(f: str, all_fields: dict) -> bool:
    fo = all_fields.get(f)
    if not fo:
        return False
    try:
        return fo._Field__sql_type.lower().strip() == 'text'
    except AttributeError:
        return False


def _is_required(f: str, all_fields: dict) -> bool:
    fo = all_fields.get(f)
    return bool(fo and fo.is_not_null() and fo.has_default_value is None)


def _is_server_generated(f: str, all_fields: dict) -> bool:
    fo = all_fields.get(f)
    if not fo or fo.has_default_value is None:
        return False
    dv = fo.has_default_value.lower().strip()
    return dv.startswith('current') or dv in ('now()', 'clock_timestamp()')


def _input_type(f: str, all_fields: dict) -> str:
    if f not in all_fields:
        return 'text'
    fo = all_fields[f]
    t = _py_type_str(fo.py_type)
    if t == 'datetime.datetime':
        return 'datetime-local'
    if t == 'datetime.date':
        return 'date'
    try:
        sql = fo._Field__sql_type.lower()
        if 'timestamp' in sql:
            return 'datetime-local'
        if sql == 'date':
            return 'date'
    except AttributeError:
        pass
    return 'text'


def _text_fields(field_names: list, all_fields: dict) -> str:
    """Return a JS/TS set literal body: 'field1', 'field2', ..."""
    text = [f for f in field_names if _is_text_field(f, all_fields)]
    return ', '.join(repr(f) for f in text)


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------

class StoreGenerator(ABC):

    PY_TO_TS = {
        'str':               'string',
        'int':               'number',
        'float':             'number',
        'bool':              'boolean',
        'uuid.UUID':         'string',
        'datetime.datetime': 'string',
        'datetime.date':     'string',
        'datetime.time':     'string',
        'datetime.timedelta':'string',
        'decimal.Decimal':   'number',
    }

    def ts_type(self, py_type_str: str) -> str:
        return self.PY_TO_TS.get(py_type_str, 'unknown')

    def resource_name(self, schema: str, table: str) -> str:
        """blogAuthor (camelCase)"""
        return _rname(schema, table)

    def interface_name(self, schema: str, table: str) -> str:
        """BlogAuthor (PascalCase)"""
        return _cname(schema, table)

    def _fk_deps(self, inst, out_names: list, crud_resources: set) -> list:
        """Return (local_field, remote_schema, remote_table, remote_pk) for each
        simple non-reverse FK whose local field is in out_names and whose remote
        table is in crud_resources."""
        deps = []
        for fk in getattr(inst, '_ho_fkeys', {}).values():
            if fk.is_reverse:
                continue
            local_fields = fk.names
            remote_pks   = fk.fk_names
            if len(local_fields) != 1 or len(remote_pks) != 1:
                continue
            local_field = local_fields[0]
            if local_field not in out_names:
                continue
            fqtn = fk.remote['fqtn']
            remote_schema = fqtn[0].replace('.', '_')
            # "half_orm_meta.identity" is a schema whose name legitimately
            # contains a literal dot (not a hierarchical separator to
            # flatten, unlike the general case this .replace() targets) —
            # undo the mangling for it specifically so it matches the real
            # runtime resource key ("half_orm_meta.identity/user", used by
            # both the generated backend route and the frontend's
            # SiloRegistry, neither of which mangle it) instead of a key
            # nothing actually uses. See planning/a_resoudre.md item 18.
            if remote_schema == 'half_orm_meta_identity':
                remote_schema = 'half_orm_meta.identity'
            remote_table  = fqtn[1]
            if (remote_schema, remote_table) not in crud_resources:
                continue
            deps.append((local_field, remote_schema, remote_table, remote_pks[0]))
        return deps

    def _reverse_fk_deps(self, inst, pk_field: str | None, crud_resources: set) -> list:
        """Return (remote_schema, remote_table, fk_field) for each simple reverse FK
        whose remote table is in crud_resources. Deduplicated by remote table."""
        if not pk_field:
            return []
        deps = []
        seen: set[tuple[str, str]] = set()
        for fk in getattr(inst, '_ho_fkeys', {}).values():
            if not fk.is_reverse:
                continue
            our_pk_fields    = fk.names
            remote_fk_fields = fk.fk_names
            if len(our_pk_fields) != 1 or len(remote_fk_fields) != 1:
                continue
            if our_pk_fields[0] != pk_field:
                continue
            fqtn = fk.remote['fqtn']
            remote_schema = fqtn[0].replace('.', '_')
            # "half_orm_meta.identity" is a schema whose name legitimately
            # contains a literal dot (not a hierarchical separator to
            # flatten, unlike the general case this .replace() targets) —
            # undo the mangling for it specifically so it matches the real
            # runtime resource key ("half_orm_meta.identity/user", used by
            # both the generated backend route and the frontend's
            # SiloRegistry, neither of which mangle it) instead of a key
            # nothing actually uses. See planning/a_resoudre.md item 18.
            if remote_schema == 'half_orm_meta_identity':
                remote_schema = 'half_orm_meta.identity'
            remote_table  = fqtn[1]
            if (remote_schema, remote_table) not in crud_resources:
                continue
            if (remote_schema, remote_table) in seen:
                continue
            seen.add((remote_schema, remote_table))
            deps.append((remote_schema, remote_table, remote_fk_fields[0]))
        return deps

    def _association_targets(
        self, inst, pk_field: str | None, crud_resources: set,
        is_association_by_res: dict,
    ) -> list:
        """For each reverse-FK child that's a many-to-many pivot table (see
        half_orm_gen.backend.litestar.v2.runtime._pivot_fk_pair — reused
        here rather than re-derived, so both stay in lockstep with the
        backend's own /via/ route), resolve the pivot's OTHER forward FK to
        find the actual far-side target.

        Returns (pivot_schema, pivot_table, fixed_field, target_schema,
        target_table) — fixed_field is the pivot's own column referencing
        `inst` (the one path segment the backend's /via/{fixed_field}/{id}
        route needs), same value _reverse_fk_deps already resolves.
        """
        from half_orm_gen.backend.litestar.v2.runtime import _pivot_fk_pair

        targets = []
        for pivot_schema, pivot_table, fixed_field in self._reverse_fk_deps(inst, pk_field, crud_resources):
            if not is_association_by_res.get((pivot_schema, pivot_table), False):
                continue
            pivot_cls = inst._ho_model.get_relation_class(f'{pivot_schema}.{pivot_table}')
            sides = _pivot_fk_pair(pivot_cls)
            if sides is None:
                continue
            this_side = next((s for s in sides if s.field == fixed_field), None)
            if this_side is None:
                continue
            target_side = next(s for s in sides if s is not this_side)
            targets.append((pivot_schema, pivot_table, fixed_field, target_side.schema, target_side.table))
        return targets

    @abstractmethod
    def generate(self, classes, api_version, output_dir: Path, *, meta_model=None) -> None: ...