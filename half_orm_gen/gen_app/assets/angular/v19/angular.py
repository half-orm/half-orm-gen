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
from pathlib import Path

from half_orm_gen.crud_routes import (
    _gen_out_fields,
    _gen_in_fields,
    _simple_pk,
    _pk_info,
    _instance,
)
from half_orm_gen.gen_store.base import StoreGenerator

from ._static import (
    _PACKAGE_JSON, _ANGULAR_JSON, _TSCONFIG, _TSCONFIG_APP, _INDEX_HTML,
    _STYLES_CSS, _LATEX_PIPE, _TAILWIND_CONFIG, _POSTCSS_CONFIG, _MAIN_TS,
    _APP_CONFIG_TS, _STATE_REGISTRY, _proxy_conf,
)
from ._app_shell import (
    _auth_service, _app_component, _auth_guard_ts, _app_routes,
    _login_component, _access_component,
)
from ._pages import _home_component_ts, _schema_component_ts
from ._specs import _schema_component_spec_ts
from ._list_component import _list_component
from ._form_components import _create_component, _fields_component
from ._detail_component import _detail_component


# ---------------------------------------------------------------------------
# Generator class
# ---------------------------------------------------------------------------

class AngularAppGenerator(StoreGenerator):

    def generate(self, classes, api_version, output_dir: Path) -> None:
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True)

        version_prefix = f'/v{api_version}' if api_version is not None else ''
        project_name   = output_dir.name
        project_title  = ' '.join(p.capitalize() for p in project_name.split('-'))

        # --- static files ---
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
        crud_resources_map: dict[tuple[str, str], dict] = {}
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
            crud_resources_map[(schema_name, table_name)] = getattr(mod, 'CRUD_ACCESS', {})
            raw.append((relation, mod))

        # Pre-pass: compute detail_resources before Pass 2 (needed for FK link filtering)
        detail_resources: set[tuple[str, str]] = set()
        for relation, mod in raw:
            ca = getattr(mod, 'CRUD_ACCESS', None) or {'GET': {}, 'POST': {}, 'PUT': {}, 'DELETE': {}}
            if _simple_pk(relation) and 'GET' in ca:
                detail_resources.add((
                    relation._t_fqrn[1],
                    relation._t_fqrn[2],
                ))

        # Pass 2 — per-resource metadata
        resources = []
        for relation, mod in raw:
            crud_access  = getattr(mod, 'CRUD_ACCESS', None) or {'GET': {}, 'POST': {}, 'PUT': {}, 'DELETE': {}}
            api_excluded = getattr(mod, 'API_EXCLUDED_FIELDS', [])
            schema_name  = relation._t_fqrn[1]
            table_name   = relation._t_fqrn[2]
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

            has_post   = 'POST'   in crud_access and bool(pk_info)
            has_put    = 'PUT'    in crud_access and bool(pk_info)
            has_del    = 'DELETE' in crud_access and bool(pk_info)
            has_detail = 'GET'    in crud_access and bool(pk_info)

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

            resources.append((
                schema_name, table_name, map_key, iname, base_path,
                all_fields, out_names, pk_info, pk_field, pk_ts_type, pk_extractor,
                has_post, has_put, has_del, has_detail,
                post_in_names, put_in_names,
                fk_deps, rev_fk_deps,
                optional_post_fields,
            ))

        # --- auth guard ---
        self._write(app_dir / 'core' / 'auth.guard.ts', _auth_guard_ts())

        # --- stores ---
        stores_dir = app_dir / 'generated' / 'stores'
        stores_dir.mkdir(parents=True, exist_ok=True)

        # --- shared filters module ---
        package_dir = Path(__file__).parents[4]
        filters_src = package_dir / 'templates_filters.ts'
        if filters_src.exists():
            shutil.copy2(filters_src, stores_dir / 'filters.ts')
            print(f'  {stores_dir / "filters.ts"}')

        # --- shared silo files (SiloRegistry / ResourceSilo / schema types) ---
        angular_assets = Path(__file__).parent
        generated_dir = app_dir / 'generated'
        generated_dir.mkdir(parents=True, exist_ok=True)
        for fname in ('schema.types.ts', 'resource.silo.ts', 'silo-registry.service.ts'):
            src = angular_assets / fname
            if src.exists():
                shutil.copy2(src, generated_dir / fname)
                print(f'  {generated_dir / fname}')

        # --- static assets (served from public/ per angular.json) ---
        assets_src = package_dir / 'assets'
        public_dir = output_dir / 'public'
        public_dir.mkdir(parents=True, exist_ok=True)
        for asset in ('logo.png', 'angular_200x200.png'):
            shutil.copy2(assets_src / asset, public_dir / asset)

        # --- app routes + app component ---
        route_meta = [
            (r[0], r[1], r[2], r[11], r[12], r[14])  # sn, tn, mk, has_post, has_put, has_detail
            for r in resources
        ]
        first_route = f'/ho_bo/{resources[0][0]}/{resources[0][1]}' if resources else '/ho_bo'
        self._write(app_dir / 'app.routes.ts',
                    _app_routes(route_meta, first_route))
        self._write(app_dir / 'app.component.ts',
                    _app_component([(r[0], r[1]) for r in resources], version_prefix=version_prefix))

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

        # --- per-resource generated components ---
        for (schema_name, table_name, map_key, iname, base_path,
             all_fields, out_names, pk_info, pk_field, pk_ts_type, pk_extractor,
             has_post, has_put, has_del, has_detail,
             post_in_names, put_in_names,
             fk_deps, rev_fk_deps,
             optional_post_fields) in resources:

            comp_dir = app_dir / 'generated' / 'components' / f'{schema_name}_{table_name}'

            ts, html, css = _list_component(schema_name, table_name, iname, map_key,
                                             out_names, pk_field, pk_ts_type, pk_extractor,
                                             has_post, has_del, fk_deps, all_fields, pk_info)
            self._write(comp_dir / 'list.component.ts', ts)
            self._write(comp_dir / 'list.component.html', html)
            self._write(comp_dir / 'list.component.css', css)

            if has_post:
                ts, html, css = _create_component(schema_name, table_name, iname,
                                                   post_in_names, all_fields, optional_post_fields)
                self._write(comp_dir / 'create.component.ts', ts)
                self._write(comp_dir / 'create.component.html', html)
                self._write(comp_dir / 'create.component.css', css)

            if has_detail:
                ts, html, css = _fields_component(schema_name, table_name, iname,
                                                   pk_field, pk_cols, out_names, fk_deps, all_fields)
                self._write(comp_dir / 'fields.component.ts', ts)
                self._write(comp_dir / 'fields.component.html', html)
                self._write(comp_dir / 'fields.component.css', css)

                ts, html, css = _detail_component(schema_name, table_name, iname,
                                                   pk_field, pk_ts_type, pk_extractor,
                                                   out_names, put_in_names, has_put,
                                                   map_key, fk_deps, rev_fk_deps, all_fields)
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
