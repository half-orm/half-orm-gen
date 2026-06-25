from half_orm_gen.crud_routes import _py_type_str
from ._helpers import _selector, _title, _field_type_category


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


def _text_fields_ts(field_names: list, all_fields: dict) -> str:
    text = [f for f in field_names if _is_text_field(f, all_fields)]
    return ', '.join(repr(f) for f in text)


def _ng_form_field(f: str, all_fields: dict) -> str:
    req      = _is_required(f, all_fields)
    req_attr = ' required' if req else ''
    req_mark = ' <span class="text-red-500">*</span>' if req else ''
    itype    = _input_type(f, all_fields)
    if _is_bool_field(f, all_fields):
        return (
            f'<div class="flex items-center gap-2">\n'
            f'        <input type="checkbox" [(ngModel)]="form[\'{f}\']" name="{f}"\n'
            f'               class="h-4 w-4 rounded border-gray-300" />\n'
            f'        <label class="text-sm font-medium text-gray-700">{f}</label>\n'
            f'      </div>'
        )
    if _is_textarea_field(f, all_fields):
        return (
            f'<div>\n'
            f'        <label class="block text-sm font-medium text-gray-700 mb-1">{f}{req_mark}</label>\n'
            f'        <textarea [(ngModel)]="form[\'{f}\']" name="{f}"{req_attr}\n'
            f'                  class="w-full border rounded px-3 py-2 text-sm font-mono resize-y min-h-[1rem] [field-sizing:content]"></textarea>\n'
            f'      </div>'
        )
    return (
        f'<div>\n'
        f'        <label class="block text-sm font-medium text-gray-700 mb-1">{f}{req_mark}</label>\n'
        f'        <input type="{itype}" [(ngModel)]="form[\'{f}\']" name="{f}"{req_attr}\n'
        f'               class="w-full border rounded px-3 py-2 text-sm" />\n'
        f'      </div>'
    )


def _create_component(
    schema_name: str, table_name: str,
    iname: str,
    post_in_names: list, all_fields: dict,
    optional_post_fields: frozenset = frozenset(),
) -> tuple[str, str, str]:
    title = _title(schema_name, table_name)
    visible_post = [f for f in post_in_names if not _is_server_generated(f, all_fields)]
    fields_ts = ', '.join(
        f'{f}: false  as any' if _is_bool_field(f, all_fields) else f'{f}: \'\'  as any'
        for f in visible_post
    )

    form_fields = '\n      '.join(
        _ng_form_field(f, all_fields)
        for f in visible_post
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
        + (
            "        .filter(([k, v]) => !this.optionalFields.has(k) || v !== '')\n"
            if optional_post_fields else ""
        )
        + null_map
        + "    );\n"
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

    ts = f"""\
import {{ Component, inject, signal }} from '@angular/core';
import {{ FormsModule }} from '@angular/forms';
import {{ RouterLink, Router }} from '@angular/router';
import {{ SiloRegistry }} from '../../../generated/silo-registry.service';
import type {{ Row }} from '../../../generated/resource.silo';

@Component({{
  selector: '{_selector(schema_name, table_name, 'create')}',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './create.component.html',
  styleUrl: './create.component.css',
}})
export class {iname}CreateComponent {{
  private silo   = inject(SiloRegistry).get('{schema_name}/{table_name}');
  private router = inject(Router);
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
    fk_map = {lf: (rs, rt) for lf, rs, rt, _ in fk_deps}

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

    rows = '\n      '.join(_ro_row(f) for f in out_names)
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
import {{ Component, input }} from '@angular/core';
import {{ RouterLink }} from '@angular/router';{latex_import}
import type {{ Row }} from '../../resource.silo';

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
}}
"""
    return ts, html, ''
