from ._helpers import _selector, _title, _field_type_category


def _list_component(
    schema_name: str, table_name: str,
    iname: str, map_key: str,
    out_names: list, pk_field: str | None, pk_ts_type: str, pk_extractor: str | None,
    has_post: bool, has_del: bool,
    fk_deps: list,
    all_fields: dict,
    pk_info: list | None = None,
) -> tuple[str, str, str]:
    title  = _title(schema_name, table_name)
    fk_map = {lf: (rs, rt) for lf, rs, rt, _ in fk_deps}

    # Table headers (sortable)
    th_cols = '\n            '.join(
        f'@if (!silo.inaccessibleFields().has(\'{f}\')) {{'
        f'<th (click)="sortBy(\'{f}\')"'
        f' class="px-4 py-2 text-left text-sm font-semibold cursor-pointer select-none hover:bg-gray-200 text-gray-600">'
        f'{f} {{{{ silo.sortField() === \'{f}\' ? (silo.sortAsc() ? \'↑\' : \'↓\') : \'\' }}}}</th>'
        f'}}'
        for f in out_names
    )
    action_th = '<th class="px-2 py-2 w-16"></th>' if pk_field else ''

    # Filter row (one input per column, hidden when embedded)
    filter_inputs = '\n              '.join(
        f'@if (!silo.inaccessibleFields().has(\'{f}\') && silo.searchableFields().includes(\'{f}\')) {{'
        f'<th class="px-2 py-1">'
        f'<input [value]="localFilters()[\'{f}\'] || \'\'"'
        f' (input)="setFilter(\'{f}\', $any($event).target.value)"'
        f' placeholder="…"'
        f' class="w-full text-xs border rounded px-2 py-1" /></th>'
        f'}} @else if (!silo.inaccessibleFields().has(\'{f}\')) {{'
        f'<th class="px-2 py-1"></th>'
        f'}}'
        for f in out_names
    )
    action_filter_th = (
        '<th class="px-2 py-1">'
        '<button (click)="clearAllFilters()" '
        '[disabled]="Object.keys(localFilters()).length === 0" '
        'class="text-xs text-blue-600 hover:text-blue-800 disabled:text-gray-400 disabled:cursor-not-allowed" '
        'title="Clear all filters">✕</button>'
        '</th>'
    ) if pk_field else ''
    filter_row = (
        f'\n          @if (!embedded()) {{\n'
        f'          <tr class="bg-white border-b">\n'
        f'              {action_filter_th}\n'
        f'              {filter_inputs}\n'
        f'          </tr>\n'
        f'          }}'
    )

    def _td(f: str) -> str:
        inacc = f'silo.inaccessibleFields().has(\'{f}\')'
        if f in fk_map:
            rs, rt = fk_map[f]
            return (
                f'@if (!{inacc}) {{'
                f'<td class="px-4 py-2 text-sm">'
                f'<a [routerLink]="[\'/ho_bo/{rs}/{rt}\', String(item[\'{f}\'])]" (click)="$event.stopPropagation()"'
                f' class="text-blue-500 hover:underline font-mono text-xs truncate block" [class.max-w-xs]="!embedded()"'
                f' [title]="cellTitle(item[\'{f}\'])">{{{{ fmtCell(item[\'{f}\']) }}}}</a>'
                f'</td>'
                f'}}'
            )
        return (
            f'@if (!{inacc}) {{'
            f'<td class="px-4 py-2 text-sm" (click)="cellClick($event, $any(item)[\'{f}\'])">'
            f'<div class="truncate" [class.max-w-xs]="!embedded()" [title]="cellTitle(item[\'{f}\'])"'
            f' [class.text-blue-600]="$any(item)[\'{f}\'] != null && typeof $any(item)[\'{f}\'] === \'object\'"'
            f' [class.cursor-pointer]="$any(item)[\'{f}\'] != null && typeof $any(item)[\'{f}\'] === \'object\'">'
            f'{{{{ fmtCell(item[\'{f}\']) }}}}</div>'
            f'</td>'
            f'}}'
        )

    td_cols = '\n              '.join(_td(f) for f in out_names)

    row_click = (
        f' (click)="selectAndNavigate(getPkId(item))"'
        if pk_field else ''
    )
    cursor = ' cursor-pointer' if pk_field else ''

    action_td = ''
    if pk_field:
        action_td = (
            '\n              <td class="px-2 py-2">\n'
            '                @if (silo.canAccess("DELETE", getPkId(item))) {\n'
            f'                  <button (click)="handleDelete(getPkId(item), $event)"\n'
            '                          class="text-red-600 hover:underline text-sm">Delete</button>\n'
            '                }\n'
            '              </td>'
        )

    new_btn = ''
    if has_post:
        new_btn = (
            f'\n        @if (silo.canCreateWithFilters(filters())) {{\n'
            f'          <a [routerLink]="[\'/ho_bo/{schema_name}/{table_name}/new\']"\n'
            f'             [queryParams]="fkNewQueryParams()"\n'
            f'             class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 text-sm">\n'
            f'            New\n          </a>\n        }}'
        )


    delete_fn = ''
    if pk_field:
        delete_fn = (
            f'\n  handleDelete(id: string, e: Event): void {{\n'
            f'    e.stopPropagation();\n'
            f"    if (confirm('Delete this item?')) {{\n"
            f'      this.silo.remove(id).subscribe(() => this.silo.removeItem(String(id)));\n'
            f'    }}\n'
            f'  }}'
        )

    select_fn = ''
    if pk_field:
        select_fn = (
            f'\n  selectAndNavigate(id: string): void {{\n'
            f'    this.silo.selectedId.set(id);\n'
            f"    this.router.navigate(['/ho_bo/{schema_name}/{table_name}', id]);\n"
            f'  }}\n'
        )

    ws_effect = ''  # Store handles WS updates; list just reads reactively from store signals

    needs_router_link = has_post or bool(fk_deps)

    # single-PK: byPk accumulates all fetched rows including setItem() calls
    # composite-PK or no PK: byPk is never populated by the silo (pk=null), use items
    _is_single_pk = pk_field and (not pk_info or len(pk_info) == 1)
    if _is_single_pk:
        _fk_items_src = (
            'Array.from(this.silo.byPk().values()).filter(item =>\n'
            '          Object.entries(this.filters()).every(([k, v]) => String((item as any)[k]) === String(v)))'
        )
    else:
        _fk_items_src = (
            'this.silo.items().filter(item =>\n'
            '          Object.entries(this.filters()).every(([k, v]) => String((item as any)[k]) === String(v)))'
        )

    # Generate field type map for validation
    field_types_entries = ', '.join(
        f"'{fname}': '{_field_type_category(all_fields[fname])}'"
        for fname in out_names if fname in all_fields
    )
    field_types_map = f"""
  private readonly fieldTypes: Record<string, FieldType> = {{
    {field_types_entries}
  }};"""

    displayItems_block = f"""\
  readonly displayItems = computed(() => {{
    const hasFilters = Object.keys(this.filters()).length > 0;
    let items: Row[] = hasFilters
      ? {_fk_items_src}
      : this.silo.items();
    const lf = this.localFilters();
    if (Object.values(lf).some(v => v))
      items = items.filter(item =>
        Object.entries(lf).every(([k, v]) => matchFilter((item as any)[k], v)));
    const sf = this.silo.sortField();
    if (sf) {{
      const asc = this.silo.sortAsc();
      items = [...items].sort((a, b) => {{
        const av = String((a as any)[sf] ?? '');
        const bv = String((b as any)[sf] ?? '');
        return asc ? av.localeCompare(bv) : bv.localeCompare(av);
      }});
    }}
    return items;
  }});"""

    router_link_es  = "import { RouterLink } from '@angular/router';\n" if needs_router_link else ''
    _comp_imports = ['PermissionsMatrixComponent']
    if needs_router_link:
        _comp_imports.insert(0, 'RouterLink')
    imports_str = ', '.join(_comp_imports)
    if pk_extractor:
        # Add type annotation to lambda parameter
        typed_extractor = pk_extractor.replace('i =>', '(i: Row) =>')
        pk_id_line = f'\n  protected getPkId = {typed_extractor};'
        highlight_attrs = (
            '\n                [class.bg-blue-50]="silo.selectedId() === getPkId(item)"\n'
            '                [class.border-l-4]="silo.selectedId() === getPkId(item)"\n'
            '                [class.border-l-blue-500]="silo.selectedId() === getPkId(item)"'
        )
    else:
        pk_id_line = ''
        highlight_attrs = ''

    html = f"""\
@if (!embedded()) {{
  <div class="flex justify-between items-center mb-4">
    <h1 class="text-2xl font-bold">{title}</h1>{new_btn}
  </div>
  @if (auth.isAdmin()) {{
    <app-permissions-matrix [catalogEntry]="auth.catalog()['{map_key}'] ?? null" />
  }}
}} @else {{{new_btn and f'''
  <div class="flex justify-end py-1 pr-1">{new_btn}
  </div>''' or ''}}}
<div [class]="embedded() ? 'overflow-x-auto' : 'bg-white shadow-sm rounded-lg overflow-auto max-h-[calc(100vh-10rem)]'">
  <table class="w-full border-collapse">
    <thead [class]="embedded() ? 'bg-gray-100' : 'bg-gray-100 sticky top-0 z-10 shadow-sm'">
      <tr>
        {action_th}
        {th_cols}
      </tr>{filter_row}
    </thead>
    <tbody>
      @for (item of displayItems(); track $index) {{
        <tr #dataRow class="border-t hover:bg-gray-50{cursor}"{row_click}{highlight_attrs}>
          {action_td}
          {td_cols}
        </tr>
      }}
      @if (silo.isLoading()) {{
        <tr><td colspan="100" class="text-center py-4 text-gray-500">Loading...</td></tr>
      }}
    </tbody>
  </table>
</div>
@if (jsonDialogContent() !== null) {{
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
       (click)="jsonDialogContent.set(null)">
    <div class="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 p-6"
         (click)="$event.stopPropagation()">
      <div class="flex justify-between items-center mb-3">
        <h3 class="font-semibold text-gray-800">JSON</h3>
        <button (click)="jsonDialogContent.set(null)"
                class="text-gray-400 hover:text-gray-600 text-xl leading-none">✕</button>
      </div>
      <pre class="text-xs bg-gray-50 rounded p-4 overflow-auto max-h-[60vh] whitespace-pre-wrap">{{{{ jsonDialogContent() }}}}</pre>
    </div>
  </div>
}}
"""

    ts = f"""\
import {{ Component, computed, effect, inject, input, signal, untracked, DestroyRef, afterNextRender, ViewChildren, QueryList, ElementRef }} from '@angular/core';
import {{ takeUntilDestroyed }} from '@angular/core/rxjs-interop';
import {{ filter }} from 'rxjs';
{router_link_es}import {{ Router, ActivatedRoute }} from '@angular/router';
import {{ Location }} from '@angular/common';
import {{ SiloRegistry }} from '../../../generated/silo-registry.service';
import type {{ Row }} from '../../../generated/resource.silo';
import {{ AuthService }} from '../../../core/auth.service';
import {{ isValidFilterValue, normalizeFilterValue, matchFilter, fmtCell, cellTitle, parseFiltersFromUrl, encodeFiltersToUrlParams }} from '../../../generated/stores/filters';
import type {{ FieldType }} from '../../../generated/stores/filters';
import {{ PermissionsMatrixComponent }} from '../../../generated/permissions-matrix.component';
@Component({{
  selector: '{_selector(schema_name, table_name, 'list')}',
  standalone: true,
  imports: [{imports_str}],
  templateUrl: './list.component.html',
  styleUrl: './list.component.css',
}})
export class {iname}ListComponent {{
  protected silo   = inject(SiloRegistry).get('{map_key}');
  protected auth   = inject(AuthService);
  protected router = inject(Router);
  private route = inject(ActivatedRoute);
  private location = inject(Location);
  protected String = String;  // For template use
  protected Object = Object;  // For template use
  protected matchFilter = matchFilter;  // For template use
  protected fmtCell = fmtCell;  // For template use
  protected cellTitle = cellTitle;  // For template use{pk_id_line}
  private destroyRef = inject(DestroyRef);

  @ViewChildren('dataRow') dataRows!: QueryList<ElementRef<HTMLTableRowElement>>;
  private observer?: IntersectionObserver;
  private currentLastElement?: Element;
  private filterDebounceTimer?: number;
  private hadFilters = false;

  readonly filters  = input<Partial<Row>>({{}});
  readonly embedded = input(false);

  localFilters = signal<Record<string, string>>({{}});
{field_types_map}
{displayItems_block}

  constructor() {{
    // Initialize filters from URL or store before loading data
    this.initFiltersFromUrl();

    effect(() => {{
      const _token = this.auth.token();
      const _v    = this.auth.accessVersion();
      const _rv   = this.auth.resourceAccessVersion()['{map_key}'];
      const _sim  = this.auth.simulatedRole();
      this.silo.list(this.filters());
    }});{ws_effect}

    // Set up observer
    this.observer = new IntersectionObserver(
      (entries) => {{
        if (entries[0].isIntersecting && this.silo.hasMore() && !this.silo.isLoading()) {{
          this.silo.loadMore(this.filters());
        }}
      }},
      {{ rootMargin: '0px 0px 400px 0px' }}
    );

    // Re-observe when items change (must be in constructor for injection context)
    effect(() => {{
      this.silo.items().length;  // Track changes
      untracked(() => {{
        setTimeout(() => this.updateObservedElement(), 0);
      }});
    }});

    // Initial observation after render
    afterNextRender(() => {{
      this.updateObservedElement();
    }});

    this.destroyRef.onDestroy(() => {{
      this.observer?.disconnect();
    }});
  }}

  private updateObservedElement() {{
    if (this.currentLastElement) this.observer?.unobserve(this.currentLastElement);
    const rows = this.dataRows.toArray();
    if (rows.length > 0) {{
      const lastElement = rows[rows.length - 1].nativeElement;
      this.currentLastElement = lastElement;
      this.observer?.observe(lastElement);
    }}
  }}

  sortBy(f: string): void {{
    if (this.silo.sortField() === f) this.silo.sortAsc.set(!this.silo.sortAsc());
    else {{ this.silo.sortField.set(f); this.silo.sortAsc.set(true); }}
  }}
  setFilter(f: string, v: string): void {{
    const updated = {{ ...this.localFilters(), [f]: v }};
    this.localFilters.set(updated);

    // Apply filters on backend with debounce
    if (this.filterDebounceTimer) clearTimeout(this.filterDebounceTimer);
    this.filterDebounceTimer = window.setTimeout(() => {{
      // Convert local filters to backend search query (q=col1:val1,col2:val2)
      // Only include valid filters based on field type
      const filterPairs: string[] = [];
      Object.entries(updated).forEach(([key, val]) => {{
        if (val && isValidFilterValue(key, val, this.fieldTypes)) {{
          const normalizedVal = normalizeFilterValue(key, val, this.fieldTypes);
          filterPairs.push(`${{key}}:${{normalizedVal}}`);
        }}
      }});
      const hasFiltersNow = filterPairs.length > 0;

      // Update URL with current filters
      this.syncFiltersToUrl(updated);

      // Only trigger if we have filters now, or we had filters before (to clear them)
      if (hasFiltersNow || this.hadFilters) {{
        this.hadFilters = hasFiltersNow;
        // Reset pagination state and clear loaded filters cache
        this.silo.resetFilterState();
        const searchParams = hasFiltersNow ? {{ q: filterPairs.join(',') }} as any : {{}};
        this.silo.list(searchParams, 0);
      }}
    }}, 600);
  }}
  jsonDialogContent = signal<string | null>(null);
  showJson(v: unknown): void {{ this.jsonDialogContent.set(JSON.stringify(v, null, 2)); }}
  cellClick(e: Event, v: unknown): void {{
    if (v != null && typeof v === 'object') {{ e.stopPropagation(); this.showJson(v); }}
  }}

  private initFiltersFromUrl(): void {{
    if (this.embedded()) return; // Don't sync URL for embedded components

    const params = this.route.snapshot.queryParams;
    const urlFilters = parseFiltersFromUrl(params, this.fieldTypes);

    // If URL has filters, use them (priority)
    if (Object.keys(urlFilters).length > 0) {{
      this.localFilters.set(urlFilters);
      this.silo.filters.set(urlFilters);
    }} else {{
      // Otherwise, try to restore from store
      const storeFilters = this.silo.filters();
      if (Object.keys(storeFilters).length > 0) {{
        this.localFilters.set(storeFilters);
        // Update URL to reflect store filters
        this.syncFiltersToUrl(storeFilters);
      }}
    }}
  }}

  private syncFiltersToUrl(filters: Record<string, string>): void {{
    if (this.embedded()) return; // Don't sync URL for embedded components

    // Update store with current filters
    this.silo.filters.set(filters);

    const queryParams: Record<string, string> = {{}};

    // Preserve non-filter params
    Object.entries(this.route.snapshot.queryParams).forEach(([key, value]) => {{
      if (!key.startsWith('f_') && typeof value === 'string') {{
        queryParams[key] = value;
      }}
    }});

    // Add filter params (using shared function)
    const filterParams = encodeFiltersToUrlParams(filters, this.fieldTypes);
    Object.assign(queryParams, filterParams);

    // Use replaceState to avoid polluting browser history
    const urlTree = this.router.createUrlTree([], {{
      relativeTo: this.route,
      queryParams,
      queryParamsHandling: '' // Replace all params
    }});

    this.location.replaceState(urlTree.toString());
  }}

  clearAllFilters(): void {{
    this.localFilters.set({{}});
    this.syncFiltersToUrl({{}});
  }}

  fkNewQueryParams(): Record<string, string> {{
    const fkAuto = this.silo.fkAutoFields('POST');
    const f = this.filters();
    const params: Record<string, string> = {{}};
    for (const [field, rule] of Object.entries(fkAuto)) {{
      if (rule === 'context' && f[field] != null) params[field] = String(f[field]);
    }}
    return params;
  }}{select_fn}{delete_fn}
}}
"""
    return ts, html, ''
