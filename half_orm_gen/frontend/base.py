"""
Abstract base class for frontend store generators.
"""

from abc import ABC, abstractmethod
from pathlib import Path


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
        schema = schema.replace('.', '_')
        parts = schema.split('_') + table.split('_')
        return parts[0].lower() + ''.join(p.capitalize() for p in parts[1:])

    def interface_name(self, schema: str, table: str) -> str:
        """BlogAuthor (PascalCase)"""
        schema = schema.replace('.', '_')
        parts = schema.split('_') + table.split('_')
        return ''.join(p.capitalize() for p in parts)

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
            remote_table  = fqtn[1]
            if (remote_schema, remote_table) not in crud_resources:
                continue
            if (remote_schema, remote_table) in seen:
                continue
            seen.add((remote_schema, remote_table))
            deps.append((remote_schema, remote_table, remote_fk_fields[0]))
        return deps

    @abstractmethod
    def generate(self, classes, api_version, output_dir: Path, *, model=None) -> None: ...