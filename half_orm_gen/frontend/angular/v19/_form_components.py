from half_orm_gen.frontend.base import (
    _is_bool_field, _is_text_field, _is_textarea_field,
    _is_required, _is_server_generated, _input_type, _text_fields,
)
from ._helpers import _selector, _title, _field_type_category
from ._templates import _tpl

_text_fields_ts = _text_fields


def _ng_form_field(f: str, all_fields: dict, fk_target: tuple | None = None) -> str:
    req      = _is_required(f, all_fields)
    req_attr = ' required' if req else ''
    req_mark = ' <span class="text-red-500">*</span>' if req else ''
    itype    = _input_type(f, all_fields)
    if _is_bool_field(f, all_fields):
        default_field = _tpl('form/form_field_checkbox.html').substitute(f=f)
    elif _is_textarea_field(f, all_fields):
        default_field = _tpl('form/form_field_textarea.html').substitute(
            f=f, req_mark=req_mark, req_attr=req_attr,
        )
    else:
        default_field = _tpl('form/form_field_default.html').substitute(
            f=f, req_mark=req_mark, req_attr=req_attr, itype=itype,
        )
    if fk_target is None:
        return default_field
    rs, rt = fk_target
    target_key = f'{rs}/{rt}'
    return _tpl('form/form_field_fk_select.html').substitute(
        f=f, req_mark=req_mark, req_attr=req_attr,
        target_key=target_key, default_field=default_field,
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

    html = _tpl('form/create.component.html').substitute(
        title=title, form_fields=form_fields,
        schema_name=schema_name, table_name=table_name,
    )

    fk_effect_ts = _tpl('form/fk_effect.ts').substitute() if fk_targets_ts else ''

    ts = _tpl('form/create.component.ts').substitute(
        selector=_selector(schema_name, table_name, 'create'),
        iname=iname, schema_name=schema_name, table_name=table_name,
        fk_targets_ts=fk_targets_ts, fk_effect_ts=fk_effect_ts,
        optional_set_ts=optional_set_ts, fields_ts=fields_ts,
        submit_body=submit_body,
    )
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

    ro_row_pk_tpl = _tpl('form/ro_row_pk.html')
    ro_row_fk_tpl = _tpl('form/ro_row_fk.html')
    ro_row_latex_tpl = _tpl('form/ro_row_latex.html')
    ro_row_plain_tpl = _tpl('form/ro_row_plain.html')

    def _ro_row(f: str) -> str:
        label = f'<span class="font-medium text-gray-600 w-36 shrink-0">{f}</span>'
        if f == pk_field:
            return ro_row_pk_tpl.substitute(
                label=label, schema_name=schema_name, table_name=table_name,
                pk_id_expr=_pk_id_expr, f=f,
            )
        if f in fk_map:
            rs, rt = fk_map[f]
            return ro_row_fk_tpl.substitute(label=label, rs=rs, rt=rt, f=f)
        if f in all_fields and _field_type_category(all_fields[f]) == 'string':
            return ro_row_latex_tpl.substitute(label=label, f=f)
        return ro_row_plain_tpl.substitute(label=label, f=f)

    rows = '\n      '.join(
        f'@if (!inaccessibleFields().has(\'{f}\')) {{\n      {_ro_row(f)}\n      }}'
        for f in out_names
    )
    latex_import = "\nimport { LatexPipe } from '../../../core/latex.pipe';" if has_latex else ''
    all_imports = ', '.join(filter(None, [
        'RouterLink',
        'LatexPipe' if has_latex else '',
    ]))

    # FK label resolution: read the target row from its silo's cache if
    # already present (no fetch triggered here — see _list_component.py for
    # why an active fetch-on-demand was reverted), then format via the
    # shared `formatLabel` using the target's label_fields. Falls back to
    # the raw id if the row isn't already loaded (e.g. via the detail page's
    # own fk_fetch_effects, which populate this same silo cache) or has no
    # label_fields configured.
    fk_core_import = ''
    fk_label_imports = (
        "\nimport { formatLabel } from '../../silo-shared';"
    ) if fk_map else ''
    fk_label_block = (
        # item/field (not a pre-cast embedded label) are passed in from the
        # template — Angular's template expression grammar doesn't support
        # TS-only syntax like `as any`, so the (item['_labels'] as any)?.[f]
        # cast has to happen here, in TS, not inline in the .html.
        f'\n  fkLabel(targetKey: string, id: unknown, item: Row, field: string): string {{\n'
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

    html = _tpl('form/fields.component.html').substitute(rows=rows)

    ts = _tpl('form/fields.component.ts').substitute(
        latex_import=latex_import,
        fk_core_import=fk_core_import,
        fk_label_imports=fk_label_imports,
        fk_label_block=fk_label_block,
        selector=_selector(schema_name, table_name, 'fields'),
        all_imports=all_imports, iname=iname, map_key=map_key,
    )
    return ts, html, ''
