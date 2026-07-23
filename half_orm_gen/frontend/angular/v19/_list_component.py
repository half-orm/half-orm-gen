from ._helpers import _selector, _title, _field_type_category
from ._templates import _tpl


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
    th_col_tpl = _tpl('list/th_col.html')
    th_cols = '\n            '.join(th_col_tpl.substitute(f=f) for f in out_names)
    action_th = '<th class="px-2 py-2 w-16"></th>' if pk_field else ''

    # Filter row (one input per column, hidden when embedded)
    filter_help_item_tpl = _tpl('list/filter_help_item.html')
    filter_help_html = ''.join(
        filter_help_item_tpl.substitute(code=code, desc=desc)
        for code, desc in [
            ('text', 'starts with'),
            ('*text', 'anywhere in the field'),
            ('&gt; &lt; &gt;= &lt;=', 'numeric/date comparison'),
            ('&gt;=A&lt;=B', 'range'),
        ]
    )
    filter_input_tpl = _tpl('list/filter_input.html')
    filter_inputs = '\n              '.join(
        filter_input_tpl.substitute(f=f, filter_help_html=filter_help_html)
        for f in out_names
    )
    action_filter_th = (
        '<th class="px-2 py-1 whitespace-nowrap">'
        '<ho-tooltip>'
        '<button ho-tooltip-trigger (click)="clearAllFilters()" '
        '[disabled]="Object.keys(localFilters()).length === 0" '
        'class="text-xs text-blue-600 hover:text-blue-800 disabled:text-gray-400 disabled:cursor-not-allowed">✕</button>'
        'Clear all filters'
        '</ho-tooltip>'
        '</th>'
    ) if pk_field else ''
    filter_row = _tpl('list/filter_row.html').substitute(
        action_filter_th=action_filter_th, filter_inputs=filter_inputs,
    )

    td_fk_tpl = _tpl('list/td_fk.html')
    td_plain_tpl = _tpl('list/td_plain.html')

    def _td(f: str) -> str:
        inacc = f"(silo.inaccessibleFields().has('{f}') || (embedded() && ('{f}' in filters())))"
        if f in fk_map:
            rs, rt = fk_map[f]
            return td_fk_tpl.substitute(inacc=inacc, rs=rs, rt=rt, f=f)
        return td_plain_tpl.substitute(inacc=inacc, f=f)

    td_cols = '\n              '.join(_td(f) for f in out_names)

    row_click = ' (click)="selectAndNavigate(getPkId(item))"' if pk_field else ''
    cursor = ' cursor-pointer' if pk_field else ''

    action_td = _tpl('list/action_td.html').substitute() if pk_field else ''

    new_btn = (
        _tpl('list/new_btn.html').substitute(schema_name=schema_name, table_name=table_name)
        if has_post else ''
    )

    new_items_badge = (
        '<app-new-items-badge [count]="contextualNewCount()" [active]="showNewOnly()" '
        '(toggle)="toggleShowNewOnly()" />'
    ) if pk_extractor else ''

    embedded_actions = ''
    if new_btn or new_items_badge:
        embedded_actions = (
            f'\n  <div class="flex justify-end items-center gap-3 py-1 pr-1">{new_items_badge}{new_btn}'
            f'\n  </div>'
        )

    delete_fn = _tpl('list/delete_fn.ts').substitute() if pk_field else ''

    select_fn = (
        _tpl('list/select_fn.ts').substitute(schema_name=schema_name, table_name=table_name)
        if pk_field else ''
    )

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
    field_types_map = _tpl('list/field_types_map.ts').substitute(field_types_entries=field_types_entries)

    _new_only_filter = _tpl('list/new_only_filter.ts').substitute() if pk_extractor else ''

    _contextual_new_count = (
        '\n\n  // "New" count scoped to this list\'s own context (parent FK filter + local\n'
        "  // filters) — not the silo's resource-wide count, which would leak e.g. a new\n"
        "  // comment on a DIFFERENT post into this post's embedded comment list.\n"
        '  readonly contextualNewCount = computed(() =>\n'
        '    this.contextItems().filter(item => this.silo.isNew(this.getPkId(item))).length\n'
        '  );'
    ) if pk_extractor else ''

    display_items_block = _tpl('list/display_items_block.ts').substitute(
        fk_items_src=_fk_items_src,
        contextual_new_count=_contextual_new_count,
        new_only_filter=_new_only_filter,
    )

    router_link_es = "import { RouterLink } from '@angular/router';\n" if needs_router_link else ''
    new_items_badge_import = (
        "import { NewItemsBadgeComponent } from '../../../generated/new-items-badge.component';\n"
    ) if pk_extractor else ''

    # FK label resolution: read the target row from its silo's cache if
    # already present (no fetch triggered — a per-visible-row fetch-on-demand
    # here caused a runaway request storm: ResourceSilo.refresh()'s single-PK
    # branch never populates auth.fetchedRoutes, so there was no working
    # dedup guard against re-requesting), then format via the shared
    # `formatLabel` using the target resource's configured label_fields.
    # Falls back to the raw id if the row isn't already loaded or has no
    # label_fields configured — the backend embeds a resolved label directly
    # in list/detail responses for that case (see runtime.py), so no
    # additional network round-trip belongs here.
    fk_label_import = (
        "import { formatLabel } from '../../../generated/silo-shared';\n"
    ) if fk_map else ''
    silo_registry_lines = (
        f"protected registry = inject(SiloRegistry);\n"
        f"  protected silo     = this.registry.get('{map_key}');"
    ) if fk_map else f"protected silo   = inject(SiloRegistry).get('{map_key}');"
    fk_label_fetch_effects = ''
    fk_label_method = (
        # item/field (not a pre-cast embedded label) are passed in from the
        # template — Angular's template expression grammar doesn't support
        # TS-only syntax like `as any`, so the (item['_labels'] as any)?.[f]
        # cast has to happen here, in TS, not inline in the .html.
        f'\n\n  fkLabel(targetKey: string, id: unknown, item: Row, field: string): string {{\n'
        f'    const strId = String(id);\n'
        f'    const row = this.registry.tryGet(targetKey)?.byPk().get(strId);\n'
        f'    if (row) {{\n'
        f'      const labelFields = (this.registry.meta()[targetKey] as any)?.label_fields ?? [];\n'
        f'      if (labelFields.length) {{\n'
        f'        const label = formatLabel(row, labelFields);\n'
        f'        if (label) return label;\n'
        f'      }}\n'
        f'    }}\n'
        f'    const embeddedLabel = (item[\'_labels\'] as any)?.[field];\n'
        f'    return embeddedLabel || strId;\n'
        f'  }}'
    ) if fk_map else ''

    _comp_imports = ['PermissionsMatrixComponent', 'HoTooltipComponent']
    if pk_extractor:
        _comp_imports.append('NewItemsBadgeComponent')
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

    html = _tpl('list/list.component.html').substitute(
        title=title, new_items_badge=new_items_badge, new_btn=new_btn,
        map_key=map_key, embedded_actions=embedded_actions,
        action_th=action_th, th_cols=th_cols, filter_row=filter_row,
        cursor=cursor, row_click=row_click, highlight_attrs=highlight_attrs,
        action_td=action_td, td_cols=td_cols,
    )

    ts = _tpl('list/list.component.ts').substitute(
        router_link_es=router_link_es,
        new_items_badge_import=new_items_badge_import,
        fk_label_import=fk_label_import,
        silo_registry_lines=silo_registry_lines,
        fk_label_fetch_effects=fk_label_fetch_effects,
        fk_label_method=fk_label_method,
        selector=_selector(schema_name, table_name, 'list'),
        imports_str=imports_str, iname=iname, map_key=map_key,
        pk_id_line=pk_id_line, field_types_map=field_types_map,
        display_items_block=display_items_block,
        select_fn=select_fn, delete_fn=delete_fn,
    )
    return ts, html, ''
