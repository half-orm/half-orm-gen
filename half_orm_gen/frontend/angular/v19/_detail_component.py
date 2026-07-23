from ._helpers import _cname, _selector, _title
from ._form_components import (
    _is_bool_field, _is_server_generated, _input_type, _text_fields_ts, _ng_form_field,
)
from ._templates import _tpl


def _assoc_slug(pivot_schema: str, pivot_table: str, fixed_field: str) -> str:
    """JS-safe unique identifier for one association_targets entry."""
    raw = f'{pivot_schema}_{pivot_table}_{fixed_field}'
    return 'assoc_' + ''.join(c if c.isalnum() else '_' for c in raw)


def _detail_component(
    schema_name: str, table_name: str,
    iname: str, pk_field: str, pk_ts_type: str, pk_extractor: str,
    out_names: list, put_in_names: list,
    has_put: bool, map_key: str,
    fk_deps: list, rev_fk_deps: list,
    all_fields: dict,
    association_targets: list | None = None,
) -> tuple[str, str, str]:
    association_targets = association_targets or []
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
        'PermissionsMatrixComponent',
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
    form_effect = ''

    visible_put = [f for f in put_in_names if not _is_server_generated(f, all_fields)]

    if has_put and visible_put:
        form_field_wrapper_tpl = _tpl('detail/form_field_wrapper.html')
        form_fields_tmpl = '\n        '.join(
            form_field_wrapper_tpl.substitute(
                field=f,
                rendered_field=_ng_form_field(f, all_fields).replace('\n        ', '\n          '),
            )
            for f in visible_put
        )
        form_init = ', '.join(
            f'{f}: false as any' if _is_bool_field(f, all_fields) else f'{f}: \'\' as any'
            for f in visible_put
        )
        form_class = f'  form: any = {{ {form_init} }};'
        edit_btn_tmpl = _tpl('detail/edit_btn.html').substitute()

        def _effect_assign(f: str) -> str:
            if _is_bool_field(f, all_fields):
                return f'this.form.{f} = Boolean((i as any).{f});'
            if _input_type(f, all_fields) == 'datetime-local':
                return f'this.form.{f} = (i as any).{f} ? String((i as any).{f}).slice(0, 16) : \'\';'
            return f'this.form.{f} = (i as any).{f} ?? \'\';'

        effect_body = ' '.join(_effect_assign(f) for f in visible_put)
        form_effect = f'\n    effect(() => {{ const i = this.item(); if (i) {{ {effect_body} }} }});'

        edit_section_tmpl = _tpl('detail/edit_section.html').substitute(
            fields_selector=fields_selector,
            form_fields_tmpl=form_fields_tmpl,
        )

    # FK reference sections — all linkable deps; self-refs reuse this.silo (already injected)
    fk_section_tpl = _tpl('detail/fk_section.html')
    fk_sections = ''
    for lf, rs, rt, remote_pk in fk_deps:
        fk_sections += fk_section_tpl.substitute(
            lf=lf, rs=rs, rt=rt,
            fk_key=f'{rs}/{rt}',
            rt_title=_title(rs, rt),
            fk_fields_sel=_selector(rs, rt, 'fields'),
        )

    # Reverse FK sections
    rev_section_tpl = _tpl('detail/rev_section.html')
    rev_sections = ''
    for rs, rt, fk_field in rev_fk_deps:
        rev_sections += rev_section_tpl.substitute(
            rs=rs, rt=rt, fk_field=fk_field,
            rt_title=_title(rs, rt),
            list_sel=_selector(rs, rt, 'list'),
            pk_field=pk_field,
        )

    # Association (many-to-many pivot) sections — the pivot's far side,
    # not its own raw rows (see runtime._pivot_fk_pair / the /via/ route).
    assoc_section_tpl = _tpl('detail/association_section.html')
    assoc_sections = ''
    assoc_signal_names = []
    for pivot_schema, pivot_table, fixed_field, target_schema, target_table, via_path in association_targets:
        signal_name = _assoc_slug(pivot_schema, pivot_table, fixed_field)
        assoc_signal_names.append((signal_name, via_path))
        assoc_sections += assoc_section_tpl.substitute(
            target_rs=target_schema, target_rt=target_table,
            target_title=_title(target_schema, target_table),
            pivot_rs=pivot_schema, pivot_rt=pivot_table,
            pivot_title=_title(pivot_schema, pivot_table),
            signal_name=signal_name,
        )

    right_col = ''
    if fk_deps:
        right_col += '\n      <p class="mt-4 px-1 text-xs font-semibold uppercase tracking-wide text-gray-400">↗ Direct references</p>'
        right_col += fk_sections
    if rev_fk_deps or association_targets:
        if fk_deps:
            right_col += '\n      <hr class="my-6 border-gray-200">'
        right_col += '\n      <p class="mt-4 px-1 text-xs font-semibold uppercase tracking-wide text-gray-400">↙ Related</p>'
        right_col += rev_sections
        right_col += assoc_sections

    handle_update = ''
    if has_put and put_in_names:
        put_text_fields_ts = _text_fields_ts(put_in_names, all_fields)
        handle_update = (
            f'\n  handleUpdate(): void {{\n'
            f"    const textFields = new Set<string>([{put_text_fields_ts}]);\n"
            f'    const putPayload = Object.fromEntries(\n'
            f'      Object.entries(this.form as unknown as Record<string, unknown>)\n'
            f"        .filter(([k]) => !this.silo.inaccessibleFields('PUT').has(k))\n"
            f'        .map(([k, v]): [string, unknown] => [k, !textFields.has(k) && v === \'\' ? null : v])\n'
            f'    );\n'
            f'    this.silo.update(this.id(), putPayload).subscribe({{\n'
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
        f"      filter(ev => ev.resource === '{map_key}' && String(ev.id) === this.id() && ev.event === 'delete'),\n"
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

    # Association (many-to-many pivot) fetch — a dedicated HttpClient call
    # (not the ResourceSilo/list machinery: the /via/ route's merged-row
    # shape isn't a normal resource list), gated on the same reactive
    # dependencies (token/access/simulated role) as the constructor's own
    # silo-fetch effect above, so it refreshes on role simulation too.
    association_imports = (
        "\nimport { HttpClient, HttpHeaders } from '@angular/common/http';"
        if assoc_signal_names else ''
    )
    association_signals = '\n  '.join(
        f'readonly {name} = signal<any[]>([]);' for name, _ in assoc_signal_names
    )
    if assoc_signal_names:
        association_signals = (
            '  private http = inject(HttpClient);\n  ' + association_signals
        )
    association_effects = ''
    for signal_name, via_path in assoc_signal_names:
        association_effects += (
            f'\n    effect(() => {{\n'
            f'      void this.auth.token();\n'
            f'      void this.auth.simulatedRole();\n'
            f'      const i = this.item();\n'
            f"      const id = i?.['{pk_field}'];\n"
            f'      if (id == null) return;\n'
            f'      const t = this.auth.token();\n'
            f"      const headers = t ? new HttpHeaders({{ Authorization: `Bearer ${{t}}` }}) : new HttpHeaders();\n"
            f"      this.http.get<{{ data: any[] }}>(`{via_path}/${{String(id)}}`, {{ headers }}).subscribe({{\n"
            f'        next: (res) => this.{signal_name}.set(res.data ?? []),\n'
            f'        error: () => this.{signal_name}.set([]),\n'
            f'      }});\n'
            f'    }});'
        )

    # Add type annotation to lambda parameter
    typed_extractor = pk_extractor.replace('i =>', '(i: Row) =>')
    pk_id_line = f'\n  protected getPkId = {typed_extractor};'

    html = _tpl('detail/detail.component.html').substitute(
        map_key=map_key, schema_name=schema_name, table_name=table_name,
        title=title, edit_btn_tmpl=edit_btn_tmpl,
        edit_section_tmpl=edit_section_tmpl, right_col=right_col,
    )

    ts = _tpl('detail/detail.component.ts').substitute(
        fk_fields_imports=fk_fields_imports, rev_list_imports=rev_list_imports,
        iname=iname, all_imports=all_imports, schema_name=schema_name,
        table_name=table_name, map_key=map_key, pk_id_line=pk_id_line,
        form_class=form_class, form_effect=form_effect, ws_effect=ws_effect,
        fk_fetch_effects=fk_fetch_effects, handle_update=handle_update,
        selector=_selector(schema_name, table_name, 'detail'),
        association_imports=association_imports,
        association_signals=association_signals,
        association_effects=association_effects,
    )
    return ts, html, ''
