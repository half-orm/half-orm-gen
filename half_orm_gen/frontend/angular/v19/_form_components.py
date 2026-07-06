from half_orm_gen.frontend.base import (
    _is_bool_field, _is_text_field, _is_textarea_field,
    _is_required, _is_server_generated, _input_type, _text_fields,
    NO_COMPONENT_FK_TARGETS,
)
from ._helpers import _selector, _title, _field_type_category

_text_fields_ts = _text_fields


def _ng_form_field(f: str, all_fields: dict, fk_target: tuple | None = None) -> str:
    req      = _is_required(f, all_fields)
    req_attr = ' required' if req else ''
    req_mark = ' <span class="text-red-500">*</span>' if req else ''
    itype    = _input_type(f, all_fields)
    if _is_bool_field(f, all_fields):
        default_field = (
            f'<div class="flex items-center gap-2">\n'
            f'        <input type="checkbox" [(ngModel)]="form[\'{f}\']" name="{f}"\n'
            f'               class="h-4 w-4 rounded border-gray-300" />\n'
            f'        <label class="text-sm font-medium text-gray-700">{f}</label>\n'
            f'      </div>'
        )
    elif _is_textarea_field(f, all_fields):
        default_field = (
            f'<div>\n'
            f'        <label class="block text-sm font-medium text-gray-700 mb-1">{f}{req_mark}</label>\n'
            f'        <textarea [(ngModel)]="form[\'{f}\']" name="{f}"{req_attr}\n'
            f'                  class="w-full border rounded px-3 py-2 text-sm font-mono resize-y min-h-[1rem] [field-sizing:content]"></textarea>\n'
            f'      </div>'
        )
    else:
        default_field = (
            f'<div>\n'
            f'        <label class="block text-sm font-medium text-gray-700 mb-1">{f}{req_mark}</label>\n'
            f'        <input type="{itype}" [(ngModel)]="form[\'{f}\']" name="{f}"{req_attr}\n'
            f'               class="w-full border rounded px-3 py-2 text-sm" />\n'
            f'      </div>'
        )
    if fk_target is None:
        return default_field
    rs, rt = fk_target
    target_key = f'{rs}/{rt}'
    return (
        f"@if (silo.fkAutoFields('POST')['{f}'] === 'select') {{\n"
        f'      <div class="relative">\n'
        f'        <label class="block text-sm font-medium text-gray-700 mb-1">{f}{req_mark}</label>\n'
        f'        <input type="hidden" [(ngModel)]="form[\'{f}\']" name="{f}"{req_attr} />\n'
        f'        <input type="text" placeholder="Type to search…"\n'
        f'               [value]="fkComboText()[\'{f}\'] ?? \'\'"\n'
        f'               (input)="onFkComboInput(\'{f}\', \'{target_key}\', $any($event.target).value)"\n'
        f'               (focus)="openFkCombo(\'{f}\')" (blur)="closeFkCombo(\'{f}\')"\n'
        f'               class="w-full border rounded px-3 py-2 text-sm" />\n'
        f"        @if (fkComboOpen()['{f}']) {{\n"
        f'        <div class="absolute z-10 mt-1 w-full bg-white border rounded-lg shadow-lg max-h-56 overflow-y-auto">\n'
        f"          @for (opt of fkOptions('{target_key}'); track opt.id) {{\n"
        f"            <div (mousedown)=\"selectFkOption('{f}', opt)\"\n"
        f'                 class="px-3 py-1.5 text-sm hover:bg-blue-50 cursor-pointer">{{{{ opt.label }}}}</div>\n'
        f'          }} @empty {{\n'
        f'            <div class="px-3 py-1.5 text-sm text-gray-400">No match</div>\n'
        f'          }}\n'
        f'        </div>\n'
        f'        }}\n'
        f'      </div>\n'
        f'    }} @else {{\n'
        f'      {default_field}\n'
        f'    }}'
    )


def _create_component(
    schema_name: str, table_name: str,
    iname: str,
    post_in_names: list, all_fields: dict,
    optional_post_fields: frozenset = frozenset(),
    fk_deps: list = (),
) -> tuple[str, str, str]:
    title = _title(schema_name, table_name)
    visible_post = [f for f in post_in_names if not _is_server_generated(f, all_fields)]
    fk_map = {lf: (rs, rt) for lf, rs, rt, _ in fk_deps}
    fields_ts = ', '.join(
        f'{f}: false  as any' if _is_bool_field(f, all_fields) else f'{f}: \'\'  as any'
        for f in visible_post
    )

    form_fields = '\n      '.join(
        f"@if (!silo.inaccessibleFields('POST').has('{f}')) {{\n      "
        + _ng_form_field(f, all_fields, fk_map.get(f))
        + '\n      }'
        for f in visible_post
    )

    fk_targets_ts = ', '.join(
        f"'{f}': '{rs}/{rt}'" for f, (rs, rt) in fk_map.items() if f in visible_post
    )

    optional_set_ts = (
        f"  private readonly optionalFields = new Set([{', '.join(repr(f) for f in sorted(optional_post_fields))}]);\n"
        if optional_post_fields else ''
    )
    text_fields_ts  = _text_fields_ts(visible_post, all_fields)
    null_map = "        .map(([k, v]): [string, unknown] => [k, !textFields.has(k) && v === '' ? null : v])\n"

    submit_body = (
        f"    const textFields = new Set<string>([{text_fields_ts}]);\n"
        "    const payload = Object.fromEntries(\n"
        "      Object.entries(this.form as unknown as Record<string, unknown>)\n"
        "        .filter(([k]) => !this.silo.inaccessibleFields('POST').has(k))\n"
        + (
            "        .filter(([k, v]) => !this.optionalFields.has(k) || v !== '')\n"
            if optional_post_fields else ""
        )
        + null_map
        + "    );\n"
        "    const fkAuto = this.silo.fkAutoFields('POST');\n"
        "    for (const [field, rule] of Object.entries(fkAuto)) {\n"
        "      if (rule === 'context') {\n"
        "        const val = this.route.snapshot.queryParamMap.get(field);\n"
        "        if (val != null) payload[field] = val;\n"
        "      }\n"
        "    }\n"
        "    this.silo.create(payload).subscribe({"
    )

    html = f"""\
<div class="max-w-lg mx-auto p-6 bg-white rounded-lg shadow mt-6">
  <h1 class="text-2xl font-bold mb-6">New {title}</h1>
  @if (error()) {{ <p class="text-red-600 mb-4">{{{{ error() }}}}</p> }}
  <form #ngForm="ngForm" (ngSubmit)="handleSubmit()" class="space-y-4">
    {form_fields}
    <div class="flex gap-3 pt-2">
      <button type="submit" [disabled]="ngForm.invalid"
              class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 text-sm disabled:opacity-50 disabled:cursor-not-allowed">
        Create
      </button>
      <a routerLink="/ho_bo/{schema_name}/{table_name}"
         class="px-4 py-2 border rounded hover:bg-gray-50 text-sm">Cancel</a>
    </div>
  </form>
</div>
"""

    fk_effect_ts = (
        f"""
  constructor() {{
    effect(() => {{
      const fkAuto = this.silo.fkAutoFields('POST');
      for (const [field, target] of Object.entries(this.fkTargets)) {{
        if (fkAuto[field] === 'select') this.registry.get(target).list();
      }}
    }});
  }}"""
        if fk_targets_ts else ''
    )

    ts = f"""\
import {{ Component, effect, inject, signal }} from '@angular/core';
import {{ FormsModule }} from '@angular/forms';
import {{ RouterLink, Router, ActivatedRoute }} from '@angular/router';
import {{ SiloRegistry }} from '../../../generated/silo-registry.service';
import {{ formatLabel }} from '../../../generated/silo-shared';
import type {{ Row }} from '../../../generated/resource.silo';

@Component({{
  selector: '{_selector(schema_name, table_name, 'create')}',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './create.component.html',
  styleUrl: './create.component.css',
}})
export class {iname}CreateComponent {{
  protected registry = inject(SiloRegistry);
  protected silo = this.registry.get('{schema_name}/{table_name}');
  private router = inject(Router);
  private route  = inject(ActivatedRoute);
  private readonly fkTargets: Record<string, string> = {{{fk_targets_ts}}};

  private fkFilterTerms = signal<Record<string, string | undefined>>({{}});

  fkOptions(targetKey: string): {{id: string; label: string}}[] {{
    const targetSilo = this.registry.tryGet(targetKey);
    if (!targetSilo) return [];
    const labelFields = (this.registry.meta()[targetKey] as any)?.label_fields ?? [];
    const term = (this.fkFilterTerms()[targetKey] ?? '').trim().toLowerCase();
    return targetSilo.items()
      .map(item => ({{id: targetSilo.pkValue(item) ?? '', label: formatLabel(item, labelFields)}}))
      .filter(opt => opt.id !== '')
      .filter(opt => !term || opt.label.toLowerCase().includes(term));
  }}

  private fkFilterTimers: Record<string, ReturnType<typeof setTimeout>> = {{}};

  onFkFilter(targetKey: string, term: string): void {{
    // Instant client-side narrowing of already-loaded options (like the list view's
    // localFilters), independent of the debounced server round-trip below.
    this.fkFilterTerms.update(t => ({{ ...t, [targetKey]: term }}));

    const targetSilo = this.registry.tryGet(targetKey);
    if (!targetSilo) return;
    if (this.fkFilterTimers[targetKey]) clearTimeout(this.fkFilterTimers[targetKey]);
    this.fkFilterTimers[targetKey] = setTimeout(() => {{
      const labelFields = (this.registry.meta()[targetKey] as any)?.label_fields ?? [];
      const trimmed = term.trim();
      targetSilo.resetFilterState();
      const q = trimmed && labelFields.length
        ? labelFields.map((f: string) => `${{f}}:*${{trimmed}}`).join(',')
        : '';
      targetSilo.list(q ? ({{q}} as any) : {{}}, 0);
    }}, 300);
  }}

  // Custom combobox (not a native <select>): keyed by field name, since several
  // fields could in principle target the same resource.
  fkComboOpen = signal<Record<string, boolean | undefined>>({{}});
  fkComboText = signal<Record<string, string | undefined>>({{}});

  openFkCombo(field: string): void {{
    this.fkComboOpen.update(o => ({{ ...o, [field]: true }}));
  }}

  closeFkCombo(field: string): void {{
    // Delay so a (mousedown) selection on an option registers before blur closes the list.
    setTimeout(() => this.fkComboOpen.update(o => ({{ ...o, [field]: false }})), 150);
  }}

  onFkComboInput(field: string, targetKey: string, term: string): void {{
    this.fkComboText.update(t => ({{ ...t, [field]: term }}));
    (this.form as any)[field] = '';
    this.fkComboOpen.update(o => ({{ ...o, [field]: true }}));
    this.onFkFilter(targetKey, term);
  }}

  selectFkOption(field: string, opt: {{id: string; label: string}}): void {{
    (this.form as any)[field] = opt.id;
    this.fkComboText.update(t => ({{ ...t, [field]: opt.label }}));
    this.fkComboOpen.update(o => ({{ ...o, [field]: false }}));
  }}
{fk_effect_ts}
{optional_set_ts}
  form: Partial<Row> = {{ {fields_ts} }};
  readonly error = signal('');

  handleSubmit(): void {{
    {submit_body}
      next: (item) => {{
        this.silo.setItem(item);
        void this.router.navigate(['/ho_bo/{schema_name}/{table_name}']);
      }},
      error: (err: Error) => this.error.set(err.message),
    }});
  }}
}}
"""
    return ts, html, ''


def _fields_component(
    schema_name: str, table_name: str,
    iname: str, pk_field: str, pk_info: list,
    out_names: list, fk_deps: list, all_fields: dict,
) -> tuple[str, str, str]:
    fk_map  = {lf: (rs, rt) for lf, rs, rt, _ in fk_deps}
    map_key = f'{schema_name}/{table_name}'

    if pk_field and len(pk_info) > 1:
        _pk_id_expr = " + '::' + ".join(
            f"'{c}:' + String(item()['{c}'])" for c, _, _ in pk_info
        )
    elif pk_field:
        _pk_id_expr = f"String(item()['{pk_field}'])"
    else:
        _pk_id_expr = ""

    has_latex = any(
        f not in fk_map and f != pk_field and f in all_fields
        and _field_type_category(all_fields[f]) == 'string'
        for f in out_names
    )

    def _ro_row(f: str) -> str:
        label = f'<span class="font-medium text-gray-600 w-36 shrink-0">{f}</span>'
        if f == pk_field:
            return (
                f'@if (!hidePk()) {{\n'
                f'      <div class="flex gap-2 items-baseline">{label}'
                f'<a [routerLink]="[\'/ho_bo/{schema_name}/{table_name}/\' + {_pk_id_expr}]"'
                f' class="font-mono text-xs text-blue-500 hover:underline break-all">{{{{ item()[\'{f}\'] }}}}</a></div>\n'
                f'    }}'
            )
        if f in fk_map:
            rs, rt = fk_map[f]
            if (rs, rt) in NO_COMPONENT_FK_TARGETS:
                # No generated detail route for this target (e.g.
                # half_orm_meta.identity/user) — plain text, not a dead link.
                return (
                    f'<div class="flex gap-2 items-baseline">{label}'
                    f'<span class="font-mono text-xs text-gray-500">{{{{ item()[\'{f}\'] }}}}</span></div>'
                )
            return (
                f'<div class="flex gap-2 items-baseline">{label}'
                f'<a [routerLink]="[\'/ho_bo/{rs}/{rt}/\' + String(item()[\'{f}\'])]"'
                f' class="text-blue-500 hover:underline font-mono text-xs">{{{{ item()[\'{f}\'] }}}}</a></div>'
            )
        if f in all_fields and _field_type_category(all_fields[f]) == 'string':
            return (
                f'<div class="flex gap-2 items-baseline">{label}'
                f'<span class="text-sm break-all" [innerHTML]="item()[\'{f}\'] | latex"></span></div>'
            )
        return (
            f'<div class="flex gap-2 items-baseline">{label}'
            f'<span class="text-sm break-all">{{{{ item()[\'{f}\'] }}}}</span></div>'
        )

    rows = '\n      '.join(
        f'@if (!inaccessibleFields().has(\'{f}\')) {{\n      {_ro_row(f)}\n      }}'
        for f in out_names
    )
    latex_import = "\nimport { LatexPipe } from '../../../core/latex.pipe';" if has_latex else ''
    all_imports = ', '.join(filter(None, [
        'RouterLink',
        'LatexPipe' if has_latex else '',
    ]))

    html = f"""\
<div class="space-y-2">
  {rows}
</div>
"""

    ts = f"""\
import {{ Component, computed, inject, input }} from '@angular/core';
import {{ RouterLink }} from '@angular/router';{latex_import}
import type {{ Row }} from '../../resource.silo';
import {{ SiloRegistry }} from '../../silo-registry.service';

@Component({{
  selector: '{_selector(schema_name, table_name, 'fields')}',
  standalone: true,
  imports: [{all_imports}],
  templateUrl: './fields.component.html',
  styleUrl: './fields.component.css',
}})
export class {iname}FieldsComponent {{
  readonly item    = input.required<Row>();
  readonly hidePk  = input<boolean>(false);
  protected String = String;
  private readonly silo = inject(SiloRegistry).tryGet('{map_key}');
  readonly inaccessibleFields = computed(() => this.silo?.inaccessibleFields() ?? new Set<string>());
}}
"""
    return ts, html, ''
