"""
Angular 22 backoffice generator.

Signal-based state (no NgRx), standalone components, Tailwind CSS.
- src/app/generated/stores/        — regenerable stores
- src/app/generated/components/    — regenerable List/Create/Detail components
- src/app/core/auth.guard.ts       — route guard (token required)
- routes use canActivate: [authGuard] for all resource pages
"""

import importlib
import shutil
from dataclasses import dataclass
from pathlib import Path

from half_orm_gen.backend.crud_routes import (
    _gen_out_fields,
    _gen_in_fields,
    _simple_pk,
    _pk_info,
    _instance,
)
from half_orm_gen.frontend.base import StoreGenerator

from ._static import (
    _PACKAGE_JSON, _ANGULAR_JSON, _TSCONFIG, _TSCONFIG_APP, _INDEX_HTML,
    _STYLES_CSS, _LATEX_PIPE, _TAILWIND_CONFIG, _POSTCSS_CONFIG, _MAIN_TS,
    _APP_CONFIG_TS, _STATE_REGISTRY, _proxy_conf, _GITIGNORE,
)
from ._app_shell import (
    _auth_service, _app_component, _auth_guard_ts, _admin_guard_ts, _app_routes,
    _login_component, _access_component,
    _ho_search_component_ts, _ho_search_component_html,
)
from ._ho_admin import _ho_admin_component_ts
from ._pages import _home_component_ts, _schema_component_ts
from ._specs import _schema_component_spec_ts
from ._list_component import _list_component
from ._form_components import _create_component, _fields_component
from ._detail_component import _detail_component
from ._permissions_matrix import (
    _permissions_matrix_component_ts,
    _permissions_fields_component_ts,
)


# ---------------------------------------------------------------------------
# Per-resource metadata container
# ---------------------------------------------------------------------------

@dataclass
class _Resource:
    schema_name: str
    table_name: str
    map_key: str
    iname: str
    base_path: str
    all_fields: dict
    out_names: list
    pk_cols: list
    pk_info: list | None
    pk_field: str | None
    pk_ts_type: str | None
    pk_extractor: str | None
    has_post: bool
    has_put: bool
    has_del: bool
    has_detail: bool
    post_in_names: list
    put_in_names: list
    fk_deps: list
    rev_fk_deps: list
    optional_post_fields: frozenset
    crud_access: dict
    api_excluded: list



# ---------------------------------------------------------------------------
# Generator class
# ---------------------------------------------------------------------------

class AngularAppGenerator(StoreGenerator):

    def generate(self, classes, api_version, output_dir: Path, *, model=None) -> None:
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True)

        version_prefix = f'/v{api_version}' if api_version is not None else ''
        project_name   = output_dir.name
        project_title  = ' '.join(p.capitalize() for p in project_name.split('-'))

        # Load all crud_access from DB in one async pass
        if model is not None:
            import asyncio
            from half_orm_gen.backend.ho_api.loader import load_crud_access

            async def _load_all():
                await model.aconnect()
                result = {}
                for relation, _kind in classes:
                    s, t = relation._t_fqrn[1], relation._t_fqrn[2]
                    ca = await load_crud_access(model, s, t)
                    result[(s, t)] = ca if ca is not None else {}
                return result

            crud_access_map = asyncio.run(_load_all())
        else:
            crud_access_map = {}

        # --- static files ---
        self._write(output_dir / '.gitignore', _GITIGNORE)
        self._write(output_dir / 'package.json',
                    _PACKAGE_JSON.format(project_name=project_name))
        self._write(output_dir / 'angular.json',
                    _ANGULAR_JSON.format(project_name=project_name))
        self._write(output_dir / 'tsconfig.json',     _TSCONFIG)
        self._write(output_dir / 'tsconfig.app.json', _TSCONFIG_APP)
        self._write(output_dir / 'tailwind.config.js', _TAILWIND_CONFIG)
        self._write(output_dir / 'postcss.config.js',  _POSTCSS_CONFIG)
        self._write(output_dir / 'proxy.conf.json',
                    _proxy_conf(version_prefix))
        self._write(output_dir / 'src' / 'index.html',
                    _INDEX_HTML.format(project_title=project_title))
        self._write(output_dir / 'src' / 'styles.css',  _STYLES_CSS)
        self._write(output_dir / 'src' / 'main.ts',     _MAIN_TS)

        app_dir = output_dir / 'src' / 'app'
        self._write(app_dir / 'app.config.ts', _APP_CONFIG_TS)
        self._write(app_dir / 'core' / 'state-registry.ts', _STATE_REGISTRY)
        self._write(app_dir / 'core' / 'auth.service.ts',
                    _auth_service(version_prefix))
        self._write(app_dir / 'core' / 'latex.pipe.ts', _LATEX_PIPE)

        # Pass 1 — identify CRUD resources
        crud_resources: set[tuple[str, str]] = set()
        raw = []
        for relation, _relation_type in classes:
            module_str = relation.__module__
            try:
                mod = importlib.import_module(module_str)
            except ImportError:
                continue
            schema_name = relation._t_fqrn[1]
            table_name  = relation._t_fqrn[2]
            crud_resources.add((schema_name, table_name))
            raw.append((relation, mod))

        # Pre-pass: compute detail_resources before Pass 2 (needed for FK link filtering)
        detail_resources: set[tuple[str, str]] = set()
        for relation, _mod in raw:
            s, t = relation._t_fqrn[1], relation._t_fqrn[2]
            if _simple_pk(relation) and 'GET' in crud_access_map.get((s, t), {}):
                detail_resources.add((s, t))

        # Pass 2 — per-resource metadata
        resources = []
        for relation, mod in raw:
            schema_name  = relation._t_fqrn[1]
            table_name   = relation._t_fqrn[2]
            crud_access  = crud_access_map.get((schema_name, table_name), {})
            api_excluded = getattr(mod, 'API_EXCLUDED_FIELDS', [])
            inst         = _instance(relation)
            all_fields   = getattr(inst, '_ho_fields', {})
            all_names    = list(all_fields.keys())
            pk_cols = _pk_info(relation)
            if len(pk_cols) == 1:
                pk_field = pk_cols[0][0]
                pk_ts_type = StoreGenerator.PY_TO_TS.get(pk_cols[0][2], 'string')
                pk_extractor = f'i => String(i[\'{pk_field}\'])'
            elif len(pk_cols) > 1:
                pk_field = pk_cols[0][0]  # first field for compatibility
                pk_ts_type = 'string'
                # New format: pk1:val1::pk2:val2
                parts = '::'.join(f'{f}:${{i[\'{f}\']}}'  for f, _, _ in pk_cols)
                pk_extractor = f'i => `{parts}`'
            else:
                pk_field = pk_ts_type = pk_extractor = None
            pk_info = pk_field  # truthy if we have a PK
            iname   = self.interface_name(schema_name, table_name)
            map_key = f'{schema_name}/{table_name}'

            out_names = _gen_out_fields(crud_access, 'GET', api_excluded, all_names)
            if not out_names:
                out_names = [f for f in all_names if f not in api_excluded]

            has_post   = bool(pk_info)
            has_put    = bool(pk_info)
            has_del    = bool(pk_info)
            has_detail = bool(pk_info)

            pk_has_default = bool(
                pk_field and all_fields.get(pk_field) and
                all_fields[pk_field].has_default_value is not None
            )
            fields_with_defaults = {
                f for f in all_names
                if all_fields.get(f) and all_fields[f].has_default_value is not None
            }
            _non_pk = [f for f in all_names
                       if (f != pk_field or not pk_has_default) and f not in api_excluded]
            post_in_names = _gen_in_fields(crud_access, 'POST', pk_field, api_excluded, all_names,
                                           pk_has_default) if has_post else []
            if has_post and not post_in_names:
                post_in_names = _non_pk
            put_in_names  = _gen_in_fields(crud_access, 'PUT',  pk_field, api_excluded, all_names) if has_put  else []
            if has_put and not put_in_names:
                put_in_names = _non_pk
            optional_post_fields = frozenset(f for f in post_in_names if f in fields_with_defaults)

            fk_deps     = self._fk_deps(inst, out_names, detail_resources)
            rev_fk_deps = self._reverse_fk_deps(inst, pk_field, crud_resources)

            base_path = f'{version_prefix}/{schema_name}/{table_name}'

            resources.append(_Resource(
                schema_name=schema_name, table_name=table_name, map_key=map_key,
                iname=iname, base_path=base_path, all_fields=all_fields,
                out_names=out_names, pk_cols=pk_cols, pk_info=pk_info, pk_field=pk_field,
                pk_ts_type=pk_ts_type, pk_extractor=pk_extractor,
                has_post=has_post, has_put=has_put, has_del=has_del, has_detail=has_detail,
                post_in_names=post_in_names, put_in_names=put_in_names,
                fk_deps=fk_deps, rev_fk_deps=rev_fk_deps,
                optional_post_fields=optional_post_fields,
                crud_access=crud_access, api_excluded=api_excluded,
            ))

        # --- guards ---
        self._write(app_dir / 'core' / 'auth.guard.ts',  _auth_guard_ts())
        self._write(app_dir / 'core' / 'admin.guard.ts', _admin_guard_ts(), once=True)

        # --- stores ---
        stores_dir = app_dir / 'generated' / 'stores'
        stores_dir.mkdir(parents=True, exist_ok=True)

        # --- shared filters module ---
        frontend_dir = Path(__file__).parents[2]
        filters_src = frontend_dir / 'templates_filters.ts'
        if filters_src.exists():
            shutil.copy2(filters_src, stores_dir / 'filters.ts')
            print(f'  {stores_dir / "filters.ts"}')

        # --- shared silo files (SiloRegistry / ResourceSilo) ---
        angular_assets = Path(__file__).parent
        generated_dir = app_dir / 'generated'
        generated_dir.mkdir(parents=True, exist_ok=True)
        for fname in ('resource.silo.ts', 'silo-registry.service.ts', 'ho-tooltip.component.ts'):
            src = angular_assets / fname
            if src.exists():
                shutil.copy2(src, generated_dir / fname)
                print(f'  {generated_dir / fname}')

        # --- cross-framework shared files (schema types / silo core logic) ---
        for fname in ('schema.types.ts', 'silo-shared.ts'):
            src = frontend_dir / fname
            if src.exists():
                shutil.copy2(src, generated_dir / fname)
                print(f'  {generated_dir / fname}')
        self._write(generated_dir / 'permissions-fields.component.ts',
                    _permissions_fields_component_ts())
        self._write(generated_dir / 'permissions-matrix.component.ts',
                    _permissions_matrix_component_ts())

        # --- static assets (served from public/ per angular.json) ---
        assets_src = Path(__file__).parents[3] / 'assets'
        public_dir = output_dir / 'public'
        public_dir.mkdir(parents=True, exist_ok=True)
        for asset in ('logo.png', 'logo-chapeau.png', 'angular_200x200.png'):
            shutil.copy2(assets_src / asset, public_dir / asset)

        # --- admin component (regenerated) ---
        admin_dir = app_dir / 'generated' / 'ho_admin'
        admin_dir.mkdir(parents=True, exist_ok=True)
        self._write(admin_dir / 'ho_admin.component.ts',
                    _ho_admin_component_ts(version_prefix))

        # --- app routes + app component ---
        route_meta = [
            (r.schema_name, r.table_name, r.map_key, r.has_post, r.has_put, r.has_detail)
            for r in resources
        ]
        first_route = (
            f'/ho_bo/{resources[0].schema_name}/{resources[0].table_name}'
            if resources else '/ho_bo'
        )
        self._write(app_dir / 'app.routes.ts',
                    _app_routes(route_meta, first_route, include_admin=True))
        self._write(app_dir / 'app.component.ts',
                    _app_component([(r.schema_name, r.table_name) for r in resources],
                                   version_prefix=version_prefix))

        # --- home + login + access pages ---
        self._write(app_dir / 'pages' / 'home'   / 'home.component.ts',
                    _home_component_ts(first_route), once=True)
        self._write(app_dir / 'pages' / 'schema' / 'schema.component.ts',
                    _schema_component_ts(), once=True)
        self._write(app_dir / 'pages' / 'schema' / 'schema.component.spec.ts',
                    _schema_component_spec_ts(), once=True)
        self._write(app_dir / 'pages' / 'login'  / 'login.component.ts',
                    _login_component(version_prefix))
        self._write(app_dir / 'pages' / 'access' / 'access.component.ts',
                    _access_component(version_prefix))
        self._write(app_dir / 'pages' / 'search' / 'ho-search.component.ts',
                    _ho_search_component_ts(version_prefix))
        self._write(app_dir / 'pages' / 'search' / 'ho-search.component.html',
                    _ho_search_component_html())

        # --- per-resource generated components ---
        for r in resources:
            comp_dir = app_dir / 'generated' / 'components' / f'{r.schema_name}_{r.table_name}'

            ts, html, css = _list_component(
                r.schema_name, r.table_name, r.iname, r.map_key,
                r.out_names, r.pk_field, r.pk_ts_type, r.pk_extractor,
                r.has_post, r.has_del, r.fk_deps, r.all_fields, r.pk_info,
            )
            self._write(comp_dir / 'list.component.ts', ts)
            self._write(comp_dir / 'list.component.html', html)
            self._write(comp_dir / 'list.component.css', css)

            if r.has_post:
                ts, html, css = _create_component(
                    r.schema_name, r.table_name, r.iname,
                    r.post_in_names, r.all_fields, r.optional_post_fields,
                    fk_deps=r.fk_deps,
                )
                self._write(comp_dir / 'create.component.ts', ts)
                self._write(comp_dir / 'create.component.html', html)
                self._write(comp_dir / 'create.component.css', css)

            if r.has_detail:
                ts, html, css = _fields_component(
                    r.schema_name, r.table_name, r.iname,
                    r.pk_field, r.pk_cols, r.out_names, r.fk_deps, r.all_fields,
                )
                self._write(comp_dir / 'fields.component.ts', ts)
                self._write(comp_dir / 'fields.component.html', html)
                self._write(comp_dir / 'fields.component.css', css)

                ts, html, css = _detail_component(
                    r.schema_name, r.table_name, r.iname,
                    r.pk_field, r.pk_ts_type, r.pk_extractor,
                    r.out_names, r.put_in_names, r.has_put,
                    r.map_key, r.fk_deps, r.rev_fk_deps, r.all_fields,
                )
                self._write(comp_dir / 'detail.component.ts', ts)
                self._write(comp_dir / 'detail.component.html', html)
                self._write(comp_dir / 'detail.component.css', css)

        print(f'\nAngular app generated in {output_dir}')
        print('Next steps:')
        print(f'  cd {output_dir}')
        print('  npm install')
        print('  npm start')

    def _write(self, path: Path, content: str, *, once: bool = False) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if once and path.exists():
            print(f'  {path}  (skipped — developer-owned)')
            return
        path.write_text(content, encoding='utf-8')
        print(f'  {path}')
