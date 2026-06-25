from ._helpers import _cname, _selector, _title
from ._form_components import (
    _is_bool_field, _is_server_generated, _input_type, _text_fields_ts, _ng_form_field,
)


def _detail_component(
    schema_name: str, table_name: str,
    iname: str, pk_field: str, pk_ts_type: str, pk_extractor: str,
    out_names: list, put_in_names: list,
    has_put: bool, map_key: str,
    fk_deps: list, rev_fk_deps: list,
    all_fields: dict,
) -> tuple[str, str, str]:
    title   = _title(schema_name, table_name)
    fk_map  = {lf: (rs, rt) for lf, rs, rt, _ in fk_deps}

    # FK store imports + injects — deduplicated: skip self-ref and multi-FK to same table
    _seen: set[str] = {f'{schema_name}_{table_name}'}
    _unique_fk_deps = []
    for dep in fk_deps:
        _, rs, rt, _ = dep
        stem = f'{rs}_{rt}'
        if stem not in _seen:
            _seen.add(stem)
            _unique_fk_deps.append(dep)

    # Reverse FK list imports
    rev_list_imports = '\n'.join(
        f"import {{ {_cname(rs, rt)}ListComponent }} from '../{rs}_{rt}/list.component';"
        for rs, rt, _ in rev_fk_deps
    )
    if rev_list_imports:
        rev_list_imports = '\n' + rev_list_imports

    rev_list_in_imports = ', '.join(f'{_cname(rs, rt)}ListComponent' for rs, rt, _ in rev_fk_deps)

    fk_fields_imports = '\n'.join(
        f"import {{ {_cname(rs, rt)}FieldsComponent }} from '../{rs}_{rt}/fields.component';"
        for _, rs, rt, _ in _unique_fk_deps
    )
    if fk_fields_imports:
        fk_fields_imports = '\n' + fk_fields_imports

    fk_fields_in_imports = ', '.join(f'{_cname(rs, rt)}FieldsComponent' for _, rs, rt, _ in _unique_fk_deps)

    all_imports = ', '.join(filter(None, [
        'RouterLink',
        f'{iname}FieldsComponent',
        fk_fields_in_imports,
        'FormsModule' if has_put and put_in_names else '',
        rev_list_in_imports,
    ]))

    fields_selector = _selector(schema_name, table_name, 'fields')

    # Edit form
    form_fields_tmpl = ''
    edit_section_tmpl = f'<{fields_selector} [item]="item()!" />'
    form_init = ''
    form_class = ''
    edit_btn_tmpl = ''
    can_edit_field = ''
    form_effect = ''

    visible_put = [f for f in put_in_names if not _is_server_generated(f, all_fields)]

    if has_put and visible_put:
        form_fields_tmpl = '\n        '.join(
            _ng_form_field(f, all_fields).replace('\n        ', '\n          ')
            for f in visible_put
        )
        form_init = ', '.join(
            f'{f}: false as any' if _is_bool_field(f, all_fields) else f'{f}: \'\' as any'
            for f in visible_put
        )
        form_class = f'  form: any = {{ {form_init} }};'
        can_edit_field = f"\n  readonly canEdit = computed(() => !!this.auth.access()['{map_key}']?.PUT);"
        edit_btn_tmpl = (
            '\n        @if (canEdit()) {\n'
            '          <button (click)="editing.set(!editing()); error.set(\'\')"'
            '\n                  class="text-sm px-3 py-1 border rounded hover:bg-gray-50">\n'
            '            {{ editing() ? \'Cancel\' : \'Edit\' }}\n'
            '          </button>\n'
            '        }'
        )
        def _effect_assign(f: str) -> str:
            if _is_bool_field(f, all_fields):
                return f'this.form.{f} = Boolean((i as any).{f});'
            if _input_type(f, all_fields) == 'datetime-local':
                return f'this.form.{f} = (i as any).{f} ? String((i as any).{f}).slice(0, 16) : \'\';'
            return f'this.form.{f} = (i as any).{f} ?? \'\';'
        effect_body = ' '.join(_effect_assign(f) for f in visible_put)
        form_effect = (
            f'\n    effect(() => {{ const i = this.item(); if (i) {{ {effect_body} }} }});'
        )
        edit_section_tmpl = f"""
    @if (!editing()) {{
      <{fields_selector} [item]="item()!" />
    }} @else {{
      @if (error()) {{ <p class="text-red-600 mb-4">{{{{ error() }}}}</p> }}
      <form #editForm="ngForm" (ngSubmit)="handleUpdate()" class="space-y-4">
        {form_fields_tmpl}
        <div class="flex gap-3 pt-2">
          <button type="submit" [disabled]="editForm.invalid"
                  class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 text-sm disabled:opacity-50 disabled:cursor-not-allowed">
            Update
          </button>
          <button type="button" (click)="editing.set(false)"
                  class="px-4 py-2 border rounded hover:bg-gray-50 text-sm">Cancel</button>
        </div>
      </form>
    }}"""

    # FK reference sections — all deps; self-refs reuse this.silo (already injected)
    fk_sections = ''
    for lf, rs, rt, remote_pk in fk_deps:
        fk_key   = f'{rs}/{rt}'
        rt_title = _title(rs, rt)
        fk_fields_sel = _selector(rs, rt, 'fields')
        fk_sections += f"""
    @if (item() && item()!['{lf}']) {{
      <div class="mt-4 p-6 bg-white rounded-lg shadow">
        <div class="flex justify-between items-center mb-3">
          <a routerLink="/ho_bo/{rs}/{rt}" class="text-lg font-semibold hover:underline hover:text-blue-700">{rt_title}</a>
        </div>
        @if (registry.tryGet('{fk_key}')?.byPk()?.get(String(item()!['{lf}'])); as ref) {{
          <{fk_fields_sel} [item]="ref!" />
        }}
      </div>
    }}"""

    # Reverse FK sections
    rev_sections = ''
    for rs, rt, fk_field in rev_fk_deps:
        cn = _cname(rs, rt)
        rt_title = _title(rs, rt)
        rev_sections += f"""
    <div class="mt-4 bg-white rounded-lg shadow overflow-hidden">
      <div class="px-6 pt-5 pb-3 flex items-center justify-between">
        <a routerLink="/ho_bo/{rs}/{rt}" class="text-lg font-semibold hover:underline hover:text-blue-700">{rt_title}</a>
        <span class="flex items-center gap-1 text-xs text-gray-400">
          <svg class="w-3.5 h-3.5 shrink-0" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M3 3a1 1 0 011-1h12a1 1 0 011 1v3a1 1 0 01-.293.707L13 10.414V15a1 1 0 01-.553.894l-4 2A1 1 0 017 17v-6.586L3.293 6.707A1 1 0 013 6V3z" clip-rule="evenodd"/>
          </svg>
          {fk_field} = {{{{ item()?.['{pk_field}'] }}}}
        </span>
      </div>
      @if (item()) {{
        <{_selector(rs, rt, 'list')} [filters]="{{ {fk_field}: String(item()!['{pk_field}']) }}" [embedded]="true" />
      }}
    </div>"""

    right_col = ''
    if fk_deps:
        right_col += '\n      <p class="mt-4 px-1 text-xs font-semibold uppercase tracking-wide text-gray-400">↗ Direct references</p>'
        right_col += fk_sections
    if rev_fk_deps:
        if fk_deps:
            right_col += '\n      <hr class="my-6 border-gray-200">'
        right_col += '\n      <p class="mt-4 px-1 text-xs font-semibold uppercase tracking-wide text-gray-400">↙ Related</p>'
        right_col += rev_sections

    handle_update = ''
    if has_put and put_in_names:
        put_text_fields_ts = _text_fields_ts(put_in_names, all_fields)
        handle_update = (
            f'\n  handleUpdate(): void {{\n'
            f"    const textFields = new Set<string>([{put_text_fields_ts}]);\n"
            f'    const putPayload = Object.fromEntries(\n'
            f'      Object.entries(this.form as unknown as Record<string, unknown>)\n'
            f'        .map(([k, v]): [string, unknown] => [k, !textFields.has(k) && v === \'\' ? null : v])\n'
            f'    );\n'
            f'    this.silo.update(this.id, putPayload).subscribe({{\n'
            f'      next: (updated) => {{\n'
            f'        this.silo.setItem(updated); this.editing.set(false);\n'
            f'        document.querySelector(\'main\')?.scrollTo({{ top: 0, behavior: \'smooth\' }});\n'
            f'      }},\n'
            f'      error: (err: Error) => this.error.set(err.message),\n'
            f'    }});\n'
            f'  }}'
        )

    ws_effect = (
        f'\n    this.auth.wsEvent$.pipe(\n'
        f"      filter(ev => ev.resource === '{map_key}' && String(ev.id) === this.id && ev.event === 'delete'),\n"
        f'      takeUntilDestroyed(),\n'
        f'    ).subscribe(() => void this.router.navigate([\'/ho_bo/{schema_name}/{table_name}\']));'
    )

    fk_fetch_effects = ''
    for lf, rs, rt, remote_pk in fk_deps:
        fk_map_key = f'{rs}/{rt}'
        fk_fetch_effects += (
            f'\n    effect(() => {{\n'
            f"      const v = this.item()?.['{lf}'];\n"
            f'      if (!v) return;\n'
            f"      const fkSilo = this.registry.tryGet('{fk_map_key}');\n"
            f'      if (fkSilo) {{\n'
            f'        const url = fkSilo.getUrl(String(v));\n'
            f'        if (!this.auth.fetchedRoutes.has(url)) fkSilo.get(String(v)).subscribe();\n'
            f'      }}\n'
            f'    }});'
        )
    own_fields_import = f"\nimport {{ {iname}FieldsComponent }} from './fields.component';"

    # Add type annotation to lambda parameter
    typed_extractor = pk_extractor.replace('i =>', '(i: Row) =>')
    pk_id_line = f'\n  protected getPkId = {typed_extractor};'

    html = f"""\
<div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6 px-4 lg:h-[calc(100vh-4rem)] lg:overflow-hidden">
  <div class="min-w-0 lg:overflow-y-auto lg:pr-1">
    @if (item()) {{
      <div class="p-6 bg-white rounded-lg shadow">
        <div class="flex justify-between items-start mb-6">
          <h1 class="text-2xl font-bold"><a routerLink="/ho_bo/{schema_name}/{table_name}" class="hover:underline hover:text-blue-700">{title}</a></h1>
          <div class="flex gap-3 items-center">{edit_btn_tmpl}
            <button (click)="location.back()" class="text-sm text-gray-500 hover:underline">← Back</button>
          </div>
        </div>
        {edit_section_tmpl}
      </div>
    }}
  </div>
  <div class="min-w-0 lg:overflow-y-auto lg:pr-1">{right_col}
  </div>
</div>
"""

    ts = f"""\
import {{ Component, computed, effect, inject, signal, untracked }} from '@angular/core';
import {{ takeUntilDestroyed }} from '@angular/core/rxjs-interop';
import {{ Location }} from '@angular/common';
import {{ filter }} from 'rxjs';
import {{ FormsModule }} from '@angular/forms';
import {{ RouterLink, Router, ActivatedRoute }} from '@angular/router';
import {{ SiloRegistry }} from '../../../generated/silo-registry.service';
import type {{ Row }} from '../../../generated/resource.silo';
import {{ AuthService }} from '../../../core/auth.service';{own_fields_import}{fk_fields_imports}{rev_list_imports}

@Component({{
  selector: '{_selector(schema_name, table_name, 'detail')}',
  standalone: true,
  imports: [{all_imports}],
  templateUrl: './detail.component.html',
  styleUrl: './detail.component.css',
}})
export class {iname}DetailComponent {{
  protected registry = inject(SiloRegistry);
  protected silo     = this.registry.get('{map_key}');
  protected auth     = inject(AuthService);
  protected router   = inject(Router);
  protected location = inject(Location);
  private route      = inject(ActivatedRoute);
  protected String = String;  // For template use{pk_id_line}

  readonly id   = this.route.snapshot.params['id'] as string;
  readonly item = computed<Row | null>(() => this.silo.byPk().get(this.id) ?? null);
{can_edit_field}
  readonly editing = signal(false);
  readonly error   = signal('');
{form_class}

  constructor() {{
    effect(() => {{
      void this.auth.token();
      if (!this.item()) untracked(() => this.silo.get(this.id as any).subscribe());
    }});{form_effect}{ws_effect}{fk_fetch_effects}
  }}

  str(v: unknown): string {{ return String(v); }}{handle_update}
}}
"""
    return ts, html, ''
