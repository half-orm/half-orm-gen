"""
Svelte 5 / TypeScript store generator (.svelte.ts, $state runes).
"""

import importlib
import shutil
from pathlib import Path

from half_orm_litestar.crud_routes import (
    _gen_out_fields,
    _gen_in_fields,
    _simple_pk,
    _instance,
    _py_type_str,
)
from half_orm_litestar.gen_store.base import StoreGenerator


class SvelteGenerator(StoreGenerator):

    def generate(self, classes, api_version, output_dir: Path) -> None:
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True)
        version_prefix = f'/v{api_version}' if api_version is not None else ''

        # Pass 1: collect resources that have CRUD_ACCESS
        resources = []
        crud_resources: set[tuple[str, str]] = set()

        for relation, _relation_type in classes:
            module_str = relation.__module__
            try:
                mod = importlib.import_module(module_str)
            except ImportError:
                continue
            crud_access = getattr(mod, 'CRUD_ACCESS', None)
            if not crud_access:
                continue
            schema_name = relation._schemaname.replace('.', '_')
            table_name  = relation.__name__.lower()
            crud_resources.add((schema_name, table_name))
            resources.append((relation, mod, crud_access, schema_name, table_name))

        # Pass 2: generate one .svelte.ts per resource
        stems = []

        for relation, mod, crud_access, schema_name, table_name in resources:
            api_excluded = getattr(mod, 'API_EXCLUDED_FIELDS', [])
            inst         = _instance(relation)
            all_fields   = getattr(inst, '_ho_fields', {})
            all_names    = list(all_fields.keys())
            pk_info      = _simple_pk(relation)
            pk_field     = pk_info[0] if pk_info else None
            pk_ts_type   = (
                self.ts_type(_py_type_str(list(inst._ho_pkey.values())[0].py_type))
                if pk_info else None
            )

            iname     = self.interface_name(schema_name, table_name)
            rname     = self.resource_name(schema_name, table_name)
            base_path = f'{version_prefix}/{schema_name}/{table_name}'
            stem      = f'{schema_name}_{table_name}'

            out_names = _gen_out_fields(crud_access, 'GET', api_excluded, all_names)
            if not out_names:
                out_names = [f for f in all_names if f not in api_excluded]

            has_post = 'POST' in crud_access and pk_info
            has_put  = 'PUT'  in crud_access and pk_info
            has_del  = 'DELETE' in crud_access and pk_info

            post_in_names = _gen_in_fields(
                crud_access, 'POST', pk_field, api_excluded, all_names
            ) if has_post else []
            put_in_names = _gen_in_fields(
                crud_access, 'PUT', pk_field, api_excluded, all_names
            ) if has_put else []

            fk_deps = self._fk_deps(inst, out_names, crud_resources)

            lines = []

            # Auth import (provides bearer token for all API calls)
            lines.append("import { auth } from '$lib/auth.svelte.ts';")
            lines.append('')

            # FK imports
            for local_field, remote_schema, remote_table, remote_pk in fk_deps:
                remote_rname = self.resource_name(remote_schema, remote_table)
                remote_stem  = f'{remote_schema}_{remote_table}'
                lines.append(
                    f"import {{ {remote_rname}State }} from './{remote_stem}.svelte.ts';"
                )
            if fk_deps:
                lines.append('')

            # Interfaces
            lines.append(self._interface(f'{iname}Out', out_names, all_fields))
            if has_post:
                lines.append(self._interface(f'{iname}PostIn', post_in_names, all_fields))
            if has_put:
                lines.append(self._interface(f'{iname}PutIn', put_in_names, all_fields))

            # State class
            lines.append(f'class {iname}State {{')
            lines.append(f'    items = $state<{iname}Out[]>([]);')
            if pk_field:
                lines.append(f'    byId  = $state(new Map<string, {iname}Out>());')
                lines.append(f'')
                lines.append(f'    setItems(data: {iname}Out[]) {{')
                lines.append(f'        this.items = data;')
                lines.append(f'        this.byId  = new Map(data.map(i => [String(i.{pk_field}), i]));')
                lines.append(f'    }}')
                lines.append(f'    setItem(item: {iname}Out) {{')
                lines.append(f'        this.byId.set(String(item.{pk_field}), item);')
                lines.append(f'        const idx = this.items.findIndex(i => i.{pk_field} === item.{pk_field});')
                lines.append(f'        if (idx >= 0) this.items[idx] = item;')
                lines.append(f'    }}')
                lines.append(f'    removeItem(id: string) {{')
                lines.append(f'        this.byId.delete(id);')
                lines.append(f'        this.items = this.items.filter(i => String(i.{pk_field}) !== id);')
                lines.append(f'    }}')

            if fk_deps:
                lines.append('')
                for local_field, remote_schema, remote_table, remote_pk in fk_deps:
                    remote_rname = self.resource_name(remote_schema, remote_table)
                    map_name = f'_{local_field}Map'
                    lines.append(
                        f'    {map_name} = $derived('
                        f'Object.fromEntries({remote_rname}State.items.map('
                        f'r => [r.{remote_pk}, r])));'
                    )
                lines.append('')
                enriched = ', '.join(
                    f'_{lf}: this._{lf}Map[item.{lf}] ?? null'
                    for lf, _, _, _ in fk_deps
                )
                lines.append(
                    f'    itemsWithRelations = $derived('
                    f'this.items.map(item => ({{...item, {enriched}}})));'
                )

            lines.append('}')
            lines.append('')
            lines.append(f'export const {rname}State = new {iname}State();')
            lines.append('')

            # API
            lines.append(f"const _BASE = '{base_path}';")
            lines.append("const _hdrs = (extra?: Record<string, string>) => ({")
            lines.append("    ...(auth.token ? { Authorization: `Bearer ${auth.token}` } : {}),")
            lines.append("    ...extra,")
            lines.append("});")
            lines.append('')
            api_entries = []
            if 'GET' in crud_access:
                api_entries.append(
                    f"    list:   (params: Partial<{iname}Out> = {{}}) =>\n"
                    f"                fetch(_BASE + '?' + new URLSearchParams(params as any),\n"
                    f"                      {{ headers: _hdrs() }}),"
                )
                if pk_info:
                    api_entries.append(
                        f"    get:    (id: {pk_ts_type}) =>\n"
                        f"                fetch(`${{_BASE}}/${{id}}`, {{ headers: _hdrs() }}),"
                    )
            if has_post:
                api_entries.append(
                    f"    create: (data: {iname}PostIn) =>\n"
                    f"                fetch(_BASE, {{ method: 'POST',\n"
                    f"                               headers: _hdrs({{'Content-Type': 'application/json'}}),\n"
                    f"                               body: JSON.stringify(data) }}),"
                )
            if has_put:
                api_entries.append(
                    f"    update: (id: {pk_ts_type}, data: {iname}PutIn) =>\n"
                    f"                fetch(`${{_BASE}}/${{id}}`, {{ method: 'PUT',\n"
                    f"                                              headers: _hdrs({{'Content-Type': 'application/json'}}),\n"
                    f"                                              body: JSON.stringify(data) }}),"
                )
            if has_del:
                api_entries.append(
                    f"    remove: (id: {pk_ts_type}) =>\n"
                    f"                fetch(`${{_BASE}}/${{id}}`,\n"
                    f"                      {{ method: 'DELETE', headers: _hdrs() }}),"
                )
            lines.append(f'export const {rname}Api = {{')
            lines.extend(api_entries)
            lines.append('};')
            lines.append('')

            out_file = output_dir / f'{stem}.svelte.ts'
            out_file.write_text('\n'.join(lines), encoding='utf-8')
            print(f'  {out_file}')
            stems.append(stem)

        if stems:
            self._write_index(output_dir, stems, version_prefix)

    def _fk_deps(self, inst, out_names: list, crud_resources: set) -> list:
        """Return (local_field, remote_schema, remote_table, remote_pk) for each
        simple non-reverse FK whose local field is in out_names and whose remote
        table has CRUD_ACCESS."""
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
            fqtn = fk.remote['fqtn']   # (schema, table)
            remote_schema = fqtn[0].replace('.', '_')
            remote_table  = fqtn[1]
            if (remote_schema, remote_table) not in crud_resources:
                continue
            deps.append((local_field, remote_schema, remote_table, remote_pks[0]))
        return deps

    def _interface(self, name: str, field_names: list, all_fields: dict) -> str:
        if not field_names:
            return f'export interface {name} {{}}\n'
        props = '\n'.join(
            f'    {f}: {self.ts_type(_py_type_str(all_fields[f].py_type))};'
            for f in field_names if f in all_fields
        )
        return f'export interface {name} {{\n{props}\n}}\n'

    def _write_index(self, output_dir: Path, stems: list, version_prefix: str) -> None:
        lines = [f"export * from './{s}.svelte.ts';" for s in stems]
        lines += [
            '',
            'export async function hoAccess(token?: string): Promise<Record<string, any>> {',
            '    const headers: Record<string, string> = token',
            '        ? { Authorization: `Bearer ${token}` }',
            '        : {};',
            f"    const res = await fetch('{version_prefix}/ho_access', {{ headers }});",
            "    if (!res.ok) throw new Error(`ho_access: ${res.status}`);",
            '    return res.json();',
            '}',
            '',
        ]
        index = output_dir / 'index.svelte.ts'
        index.write_text('\n'.join(lines), encoding='utf-8')
        print(f'  {index}')