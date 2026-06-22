"""
Svelte 5 / TypeScript store generator (.svelte.ts, $state runes).
"""

import importlib
import shutil
from pathlib import Path

from half_orm_gen.crud_routes import (
    _gen_out_fields,
    _gen_in_fields,
    _pk_info,
    _simple_pk,
    _instance,
    _py_type_str,
)
from half_orm_gen.gen_store.base import StoreGenerator


class SvelteGenerator(StoreGenerator):

    def generate(self, classes, api_version, output_dir: Path) -> None:
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True)
        self._write_base(output_dir)
        self._write_filters(output_dir)
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
            crud_access = getattr(mod, 'CRUD_ACCESS', None) or {'GET': {}, 'POST': {}, 'PUT': {}, 'DELETE': {}}
            schema_name = relation._t_fqrn[1]
            table_name  = relation._t_fqrn[2]
            crud_resources.add((schema_name, table_name))
            resources.append((relation, mod, crud_access, schema_name, table_name))

        # Pass 2: generate one .svelte.ts per resource
        stems = []

        for relation, mod, crud_access, schema_name, table_name in resources:
            api_excluded = getattr(mod, 'API_EXCLUDED_FIELDS', [])
            inst         = _instance(relation)
            all_fields   = getattr(inst, '_ho_fields', {})
            all_names    = list(all_fields.keys())
            pk_cols      = _pk_info(relation)
            pk_info      = pk_cols  # truthy iff non-empty
            if len(pk_cols) == 1:
                pk_field    = pk_cols[0][0]
                pk_ts_type  = self.ts_type(pk_cols[0][2])
                pk_extractor = f'i => String(i.{pk_field})'
            elif len(pk_cols) > 1:
                pk_field    = pk_cols[0][0]
                pk_ts_type  = 'string'
                # New format: pk1:val1::pk2:val2
                parts = '::'.join(f'{f}:${{i.{f}}}' for f, _, _ in pk_cols)
                pk_extractor = f'i => `{parts}`'
            else:
                pk_field = pk_ts_type = pk_extractor = None

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

            # Imports
            lines.append("import { BaseState } from './base.svelte.ts';")
            lines.append("import { auth } from '$lib/auth.svelte.ts';")
            lines.append("import { registerClear } from '$lib/stateRegistry';")
            lines.append('')

            # FK imports (deduplicated: skip self-referential FKs and multi-FK to same table)
            seen_stems: set[str] = {stem}
            for local_field, remote_schema, remote_table, remote_pk in fk_deps:
                remote_stem = f'{remote_schema}_{remote_table}'
                if remote_stem in seen_stems:
                    continue
                seen_stems.add(remote_stem)
                remote_rname = self.resource_name(remote_schema, remote_table)
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
            if pk_info:
                lines.append(f'class {iname}State extends BaseState<{iname}Out> {{')
                lines.append(f'    constructor() {{ super({pk_extractor}); }}')
            else:
                lines.append(f'class {iname}State {{')
                lines.append(f'    items = $state<{iname}Out[]>([]);')
                lines.append(f'    // Persisted UI state')
                lines.append(f'    filters = $state<Record<string, string>>({{}});')
                lines.append(f'    sortField = $state<string | null>(null);')
                lines.append(f'    sortAsc = $state(true);')
                lines.append(f'    setItems(data: {iname}Out[]) {{ this.items = data; }}')
                lines.append(f'    mergeItems(data: {iname}Out[]) {{ this.items = [...this.items, ...data]; }}')

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
            if pk_field:
                lines.append(f'registerClear(() => {{ {rname}State.clear(); _loadedFilters.clear(); }});')
            lines.append('')

            # API
            lines.append("const _loadedFilters = new Map<string, boolean>();")
            lines.append(f"const _BASE = '{base_path}';")
            lines.append("const _hdrs = (extra?: Record<string, string>) => ({")
            lines.append("    ...(auth.token ? { Authorization: `Bearer ${auth.token}` } : {}),")
            lines.append("    ...extra,")
            lines.append("});")
            lines.append("const _fetch = (url: string, opts?: RequestInit) => {")
            lines.append("    const method = opts?.method ?? 'GET';")
            lines.append("    if (method === 'GET') auth.fetchedRoutes.add(url);")
            lines.append("    return fetch(url, opts);")
            lines.append("};")

            lines.append('')
            api_entries = []
            if 'GET' in crud_access:
                api_entries.append(
                    f"    listUrl: (params: Partial<{iname}Out> = {{}}) => {{\n"
                    f"                 const filtered = Object.fromEntries(\n"
                    f"                   Object.entries(params)\n"
                    f"                     .filter(([_, v]) => v != null && (typeof v !== 'string' || v !== ''))\n"
                    f"                     .map(([k, v]) => [`ho_col_${{k}}`, v])\n"
                    f"                 );\n"
                    f"                 const allParams = {{...filtered, offset: '0', limit: '100'}};\n"
                    f"                 const qs = new URLSearchParams(allParams as any).toString();\n"
                    f"                 return qs ? _BASE + '?' + qs : _BASE;\n"
                    f"             }},"
                )
                api_entries.append(
                    f"    list:    async (params: Partial<{iname}Out> = {{}}, offset: number = 0): Promise<{{has_more: boolean, offset: number}}> => {{\n"
                    f"                 // Handle special 'q' param for search (not prefixed with ho_col_)\n"
                    f"                 const searchQ = (params as any)['q'];\n"
                    f"                 const filterKey = JSON.stringify(params);\n"
                    f"                 if (offset === 0 && !searchQ && _loadedFilters.get(filterKey)) return {{ has_more: false, offset }};\n"
                    f"                 const otherParams = searchQ ? {{}} : params;\n"
                    f"                 const filtered = Object.fromEntries(\n"
                    f"                   Object.entries(otherParams)\n"
                    f"                     .filter(([_, v]) => v != null && (typeof v !== 'string' || v !== ''))\n"
                    f"                     .map(([k, v]) => [`ho_col_${{k}}`, v])\n"
                    f"                 );\n"
                    f"                 const allParams: Record<string, string> = {{...filtered, offset: offset.toString(), limit: '100'}};\n"
                    f"                 if (searchQ) allParams.q = searchQ;\n"
                    f"                 const qs = new URLSearchParams(allParams as any).toString();\n"
                    f"                 const url = qs ? _BASE + '?' + qs : _BASE;\n"
                    f"                 const res = await _fetch(url, {{ headers: _hdrs() }});\n"
                    f"                 if (!res.ok) return {{ has_more: false, offset }};\n"
                    f"                 const {{ data, meta }} = await res.json();\n"
                    f"                 // For backend search (q param), merge results; otherwise replace on offset 0\n"
                    f"                 if (offset === 0 && !searchQ) {rname}State.setItems(data);\n"
                    f"                 else {rname}State.mergeItems(data);\n"
                    f"                 if (!meta.has_more) _loadedFilters.set(filterKey, true);\n"
                    f"                 return {{ has_more: meta.has_more, offset: offset + data.length }};\n"
                    f"             }},"
                )
                if pk_info:
                    api_entries.append(
                        f"    getUrl:  (id: {pk_ts_type}) => `${{_BASE}}/${{id}}`,"
                    )
                    api_entries.append(
                        f"    get:     (id: {pk_ts_type}) => {{\n"
                        f"                 const _c = {rname}State.byId.get(String(id));\n"
                        f"                 if (_c) return Promise.resolve(new Response(JSON.stringify(_c),\n"
                        f"                     {{ status: 200, headers: {{ 'Content-Type': 'application/json' }} }}));\n"
                        f"                 return _fetch(`${{_BASE}}/${{id}}`, {{ headers: _hdrs() }});\n"
                        f"             }},"
                    )
            if has_post:
                api_entries.append(
                    f"    create:  (data: {iname}PostIn) =>\n"
                    f"                 _fetch(_BASE, {{ method: 'POST',\n"
                    f"                                headers: _hdrs({{'Content-Type': 'application/json'}}),\n"
                    f"                                body: JSON.stringify(data) }}),"
                )
            if has_put:
                api_entries.append(
                    f"    update:  (id: {pk_ts_type}, data: {iname}PutIn) =>\n"
                    f"                 _fetch(`${{_BASE}}/${{id}}`, {{ method: 'PUT',\n"
                    f"                                               headers: _hdrs({{'Content-Type': 'application/json'}}),\n"
                    f"                                               body: JSON.stringify(data) }}),"
                )
            if has_del:
                api_entries.append(
                    f"    remove:  (id: {pk_ts_type}) =>\n"
                    f"                 _fetch(`${{_BASE}}/${{id}}`,\n"
                    f"                        {{ method: 'DELETE', headers: _hdrs() }}),"
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

    def _write_base(self, output_dir: Path) -> None:
        content = """\
export class BaseState<V> {
    byId  = $state(new Map<string, V>());
    items = $derived([...this.byId.values()]);

    // Persisted UI state
    filters = $state<Record<string, string>>({});  // Active filters
    selectedId = $state<string | null>(null);  // Selected item ID
    sortField = $state<string | null>(null);  // Sort field
    sortAsc = $state(true);  // Sort direction

    constructor(private readonly pk: (item: V) => string) {}

    clear() {
        this.byId = new Map();
    }
    setItems(data: V[]) {
        this.byId = new Map(data.map(i => [this.pk(i), i]));
    }
    mergeItems(data: V[]) {
        const m = new Map(this.byId);
        data.forEach(i => m.set(this.pk(i), i));
        this.byId = m;
    }
    setItem(item: V) {
        const m = new Map(this.byId);
        m.set(this.pk(item), item);
        this.byId = m;
    }
    removeItem(id: string) {
        const m = new Map(this.byId);
        m.delete(id);
        this.byId = m;
    }
}
"""
        base_file = output_dir / 'base.svelte.ts'
        base_file.write_text(content, encoding='utf-8')
        print(f'  {base_file}')

    def _write_filters(self, output_dir: Path) -> None:
        """Copy the shared filters module to the output directory."""
        import os
        # Get the path to templates_filters.ts in the package
        package_dir = Path(__file__).parent.parent
        filters_src = package_dir / 'templates_filters.ts'

        if filters_src.exists():
            filters_dst = output_dir / 'filters.ts'
            shutil.copy2(filters_src, filters_dst)
            print(f'  {filters_dst}')
        else:
            print(f'  Warning: {filters_src} not found, skipping filters module')

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