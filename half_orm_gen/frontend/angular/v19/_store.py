from half_orm_gen.backend.crud_routes import _py_type_str
from half_orm_gen.frontend.base import StoreGenerator


def _store(
    schema_name: str, table_name: str, base_path: str,
    iname: str,
    out_names: list, all_fields: dict, pk_field: str | None, pk_ts_type: str, pk_extractor: str | None,
    has_post: bool, has_put: bool, has_del: bool,
    post_in_names: list, put_in_names: list,
) -> str:
    lines = []

    lines.append("import { Injectable, signal } from '@angular/core';")
    lines.append("import { HttpClient, HttpHeaders } from '@angular/common/http';")
    lines.append("import { inject } from '@angular/core';")
    lines.append("import { catchError, filter, of, tap } from 'rxjs';")
    lines.append("import { AuthService } from '../../core/auth.service';")
    lines.append("import { registerClear, registerClearForKey } from '../../core/state-registry';")
    lines.append('')

    def _interface(name: str, field_names: list) -> list:
        result = [f'export interface {name} {{']
        for f in field_names:
            if f in all_fields:
                ts = StoreGenerator.PY_TO_TS.get(_py_type_str(all_fields[f].py_type), 'unknown')
                result.append(f'  {f}: {ts};')
        result.append('}')
        return result

    lines += _interface(f'{iname}Out', out_names)
    lines.append('')
    if has_post:
        lines += _interface(f'{iname}PostIn', post_in_names)
        lines.append('')
    if has_put:
        lines += _interface(f'{iname}PutIn', put_in_names)
        lines.append('')

    lines.append(f"const _BASE = '{base_path}';")
    lines.append('')
    lines.append(f"@Injectable({{ providedIn: 'root' }})")
    lines.append(f'export class {iname}Store {{')
    lines.append('  private auth = inject(AuthService);')
    lines.append('  private http = inject(HttpClient);')
    lines.append('')

    if pk_field:
        lines.append(f'  readonly items = signal<{iname}Out[]>([]);')
        lines.append(f'  readonly byPk  = signal(new Map<string, {iname}Out>());')
    else:
        lines.append(f'  readonly items = signal<{iname}Out[]>([]);')

    lines.append('')
    lines.append('  private loadedFilters = new Map<string, boolean>();  // Track fully loaded filter combinations')
    lines.append('  readonly hasMore = signal(true);  // Track if more data available')
    lines.append('  readonly currentOffset = signal(0);  // Current pagination offset')
    lines.append('  readonly isLoading = signal(false);  // Loading state')
    lines.append('')
    lines.append('  // Persisted UI state')
    lines.append('  readonly filters = signal<Record<string, string>>({});  // Active filters')
    lines.append('  readonly selectedId = signal<string | null>(null);  // Selected item ID')
    lines.append('  readonly sortField = signal<string | null>(null);  // Sort field')
    lines.append('  readonly sortAsc = signal(true);  // Sort direction')
    lines.append('')
    if pk_field:
        map_key_store = f'{schema_name}/{table_name}'
        lines.append(f'  constructor() {{')
        lines.append(f'    registerClear(() => this.clear());')
        lines.append(f"    registerClearForKey('{map_key_store}', () => this.clear());")
        lines.append(f"    this.auth.wsEvent$.pipe(filter(ev => ev.resource === '{map_key_store}')).subscribe(ev => {{")
        lines.append(f"      if (ev.event === 'delete') this.removeItem(String(ev.id));")
        lines.append(f"      else this.refresh(String(ev.id)).subscribe();")
        lines.append(f'    }});')
        lines.append(f'  }}')
    else:
        map_key_store = f'{schema_name}/{table_name}'
        lines.append(f"  constructor() {{")
        lines.append(f"    registerClear(() => this.clear());")
        lines.append(f"    registerClearForKey('{map_key_store}', () => this.clear());")
        lines.append(f"  }}")
    lines.append('')
    lines.append('  private get headers(): HttpHeaders {')
    lines.append('    const t = this.auth.token();')
    lines.append('    return t ? new HttpHeaders({ Authorization: `Bearer ${t}` }) : new HttpHeaders();')
    lines.append('  }')
    lines.append('')
    lines.append(f'  listUrl(params: Partial<{iname}Out> = {{}}): string {{')
    lines.append('    const filtered = Object.fromEntries(')
    lines.append('      Object.entries(params)')
    lines.append('        .filter(([_, v]) => v != null && (typeof v !== \'string\' || v !== \'\'))')
    lines.append('        .map(([k, v]) => [`ho_col_${k}`, v])')
    lines.append('    );')
    lines.append('    const qs = new URLSearchParams(filtered as any).toString();')
    lines.append('    return qs ? `${_BASE}?${qs}` : _BASE;')
    lines.append('  }')

    if pk_field:
        lines.append(f'  getUrl(id: string): string {{ return `${{_BASE}}/${{id}}`; }}')
        lines.append('')

    lines.append(f'  list(params: Partial<{iname}Out> = {{}}, offset: number = 0): void {{')
    lines.append('    const filterKey = JSON.stringify(params);')
    lines.append('    if (offset === 0 && this.loadedFilters.get(filterKey)) return;')
    lines.append('    if (this.isLoading()) return;')
    lines.append('')
    lines.append('    // Handle special \'q\' param for search (not prefixed with ho_col_)')
    lines.append('    const searchQ = (params as any)[\'q\'];')
    lines.append('    const otherParams = searchQ ? {} : params;')
    lines.append('    const baseUrl = this.listUrl(otherParams);')
    lines.append('    const separator = baseUrl.includes(\'?\') ? \'&\' : \'?\';')
    lines.append('    const urlParams = new URLSearchParams();')
    lines.append('    if (searchQ) urlParams.set(\'q\', searchQ);')
    lines.append('    if (offset > 0) urlParams.set(\'offset\', offset.toString());')
    lines.append('    urlParams.set(\'limit\', \'100\');')
    lines.append('    const queryString = urlParams.toString();')
    lines.append('    const url = queryString ? `${baseUrl}${separator}${queryString}` : baseUrl;')
    lines.append('    if (this.auth.fetchedRoutes.has(url)) return;')
    lines.append('    this.auth.fetchedRoutes.add(url);')
    lines.append('')
    lines.append('    this.isLoading.set(true);')
    lines.append(f'    this.http.get<{{data: {iname}Out[], meta: {{offset: number, limit: number, has_more: boolean}}}}>(url, {{ headers: this.headers }})')
    lines.append('      .pipe(catchError(() => of({ data: [], meta: { offset, limit: 100, has_more: false } })))')
    lines.append('      .subscribe(response => {')
    lines.append('        // Full unfiltered list replaces; filtered or paginated loads merge')
    lines.append('        if (offset === 0 && !searchQ && Object.keys(params).length === 0) this.setItems(response.data);')
    lines.append('        else this.mergeItems(response.data);')
    lines.append('        this.hasMore.set(response.meta.has_more);')
    lines.append('        this.currentOffset.set(offset + response.data.length);')
    lines.append('        this.isLoading.set(false);')
    lines.append('        if (!response.meta.has_more) this.loadedFilters.set(filterKey, true);')
    lines.append('      });')
    lines.append('  }')
    lines.append('')
    lines.append(f'  loadMore(params: Partial<{iname}Out> = {{}}): void {{')
    lines.append('    if (!this.hasMore() || this.isLoading()) return;')
    lines.append('    this.list(params, this.currentOffset());')
    lines.append('  }')
    lines.append('')
    lines.append('  resetFilterState(): void {')
    lines.append('    this.loadedFilters.clear();')
    lines.append('    this.hasMore.set(true);')
    lines.append('    this.currentOffset.set(0);')
    lines.append('  }')
    lines.append('')

    if pk_field:
        lines.append(f'  get(id: string) {{')
        lines.append('    const cached = this.byPk().get(id);')
        lines.append('    if (cached) return of(cached);')
        lines.append('    return this.refresh(id);')
        lines.append('  }')
        lines.append('')
        lines.append(f'  refresh(id: string) {{')
        lines.append('    const url = this.getUrl(id);')
        lines.append('    this.auth.fetchedRoutes.add(url);')
        lines.append(f'    return this.http.get<{iname}Out>(url, {{ headers: this.headers }}).pipe(')
        lines.append('      tap(item => this.setItem(item)),')
        lines.append(f'      catchError(() => of(null as {iname}Out | null))')
        lines.append('    );')
        lines.append('  }')
        lines.append('')

    if has_post:
        lines.append(f'  create(data: {iname}PostIn) {{')
        lines.append(f'    return this.http.post<{iname}Out>(_BASE, data, {{')
        lines.append("      headers: this.headers.append('Content-Type', 'application/json')")
        lines.append('    });')
        lines.append('  }')
        lines.append('')

    if has_put and pk_field:
        lines.append(f'  update(id: string, data: {iname}PutIn) {{')
        lines.append(f'    return this.http.put<{iname}Out>(`${{_BASE}}/${{id}}`, data, {{')
        lines.append("      headers: this.headers.append('Content-Type', 'application/json')")
        lines.append('    });')
        lines.append('  }')
        lines.append('')

    if has_del and pk_field:
        lines.append(f'  remove(id: string) {{')
        lines.append(f'    return this.http.delete(`${{_BASE}}/${{id}}`, {{ headers: this.headers }});')
        lines.append('  }')
        lines.append('')

    if pk_field:
        lines.append(f'  setItems(data: {iname}Out[]): void {{')
        lines.append('    this.items.set(data);')
        lines.append(f'    this.byPk.set(new Map(data.map(i => [({pk_extractor})(i), i])));')
        lines.append('  }')
        lines.append('')
        lines.append(f'  mergeItems(data: {iname}Out[]): void {{')
        lines.append('    const m = new Map(this.byPk());')
        lines.append(f'    data.forEach(i => m.set(({pk_extractor})(i), i));')
        lines.append('    this.byPk.set(m);')
        lines.append('    this.items.set([...m.values()]);')
        lines.append('  }')
        lines.append('')
        lines.append(f'  setItem(item: {iname}Out): void {{')
        lines.append('    const m = new Map(this.byPk());')
        lines.append(f'    m.set(({pk_extractor})(item), item);')
        lines.append('    this.byPk.set(m);')
        lines.append('    const arr = [...this.items()];')
        lines.append(f'    const idx = arr.findIndex(i => ({pk_extractor})(i) === ({pk_extractor})(item));')
        lines.append('    if (idx >= 0) arr[idx] = item; else arr.push(item);')
        lines.append('    this.items.set(arr);')
        lines.append('  }')
        lines.append('')
        lines.append('  removeItem(id: string): void {')
        lines.append('    const m = new Map(this.byPk()); m.delete(id); this.byPk.set(m);')
        lines.append(f'    this.items.set(this.items().filter(i => ({pk_extractor})(i) !== id));')
        lines.append('  }')
        lines.append('')
        lines.append('  clear(): void { this.items.set([]); this.byPk.set(new Map()); this.loadedFilters.clear(); this.hasMore.set(true); this.currentOffset.set(0); }')
    else:
        lines.append(f'  setItems(data: {iname}Out[]): void {{ this.items.set(data); }}')
        lines.append(f'  mergeItems(data: {iname}Out[]): void {{ this.items.set([...this.items(), ...data]); }}')
        lines.append('  clear(): void { this.items.set([]); this.loadedFilters.clear(); this.hasMore.set(true); this.currentOffset.set(0); }')

    lines.append('}')
    lines.append('')
    return '\n'.join(lines)
