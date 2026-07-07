from ._helpers import _cname
from ._templates import _tpl


def _auth_service(version_prefix: str) -> str:
    return _tpl('app_shell/auth.service.ts').substitute(version_prefix=version_prefix)


def _app_component(resources: list, version_prefix: str = '') -> str:
    api_base = version_prefix or '/api'
    return _tpl('app_shell/app.component.ts').substitute(version_prefix=api_base)


def _ho_search_component_ts(version_prefix: str) -> str:
    return _tpl('app_shell/ho-search.component.ts').substitute(version_prefix=version_prefix)


def _ho_search_component_html() -> str:
    return _tpl('app_shell/ho-search.component.html').substitute()


def _auth_guard_ts() -> str:
    return _tpl('app_shell/auth.guard.ts').substitute()


def _admin_guard_ts() -> str:
    return _tpl('app_shell/admin.guard.ts').substitute()


def _app_routes(resources: list, first_route: str, *, include_admin: bool = False) -> str:
    lines = [
        "import { Routes } from '@angular/router';",
    ]
    if include_admin:
        lines.append("import { adminGuard } from './core/admin.guard';")
    lines += [
        '',
        'export const routes: Routes = [',
        "  { path: '', loadComponent: () => import('./pages/home/home.component').then(m => m.HomeComponent) },",
        "  { path: 'ho_bo',  loadComponent: () => import('./pages/login/login.component').then(m => m.LoginComponent) },",
        "  { path: 'login',  loadComponent: () => import('./pages/login/login.component').then(m => m.LoginComponent) },",
        "  { path: 'access', loadComponent: () => import('./pages/access/access.component').then(m => m.AccessComponent) },",
        "  { path: 'schema', loadComponent: () => import('./pages/schema/schema.component').then(m => m.SchemaComponent) },",
    ]
    lines.append(
        "  { path: 'ho_bo/search', loadComponent: () => import('./pages/search/ho-search.component').then(m => m.HoSearchComponent) },"
    )
    lines.append(
        "  { path: 'auth/callback', loadComponent: () => import('./pages/auth-callback/auth-callback.component').then(m => m.AuthCallbackComponent) },"
    )
    lines.append(
        "  { path: 'auth/delegate', loadComponent: () => import('./pages/auth-delegate/auth-delegate.component').then(m => m.AuthDelegateComponent) },"
    )
    if include_admin:
        lines.append(
            "  { path: 'ho_bo/admin', loadComponent: () => import('./generated/ho_admin/ho_admin.component').then(m => m.HoAdminComponent), canActivate: [adminGuard] },"
        )
    route_list_tpl = _tpl('app_shell/route_list.ts')
    route_create_tpl = _tpl('app_shell/route_create.ts')
    route_detail_tpl = _tpl('app_shell/route_detail.ts')
    for sn, tn, _, has_post, _, pk_info, *__ in resources:
        cn   = _cname(sn, tn)
        stem = f'{sn}_{tn}'
        base = f'./generated/components/{stem}'
        lines.append(route_list_tpl.substitute(sn=sn, tn=tn, base=base, cn=cn))
        if has_post:
            lines.append(route_create_tpl.substitute(sn=sn, tn=tn, base=base, cn=cn))
        if pk_info:
            lines.append(route_detail_tpl.substitute(sn=sn, tn=tn, base=base, cn=cn))
    lines += ['];', '']
    return '\n'.join(lines)


def _login_component(version_prefix: str) -> str:
    return _tpl('app_shell/login.component.ts').substitute()


def _auth_callback_component() -> str:
    return _tpl('app_shell/auth-callback.component.ts').substitute()


def _auth_delegate_component(version_prefix: str) -> str:
    return _tpl('app_shell/auth-delegate.component.ts').substitute(version_prefix=version_prefix)


def _access_component(version_prefix: str) -> str:
    return _tpl('app_shell/access.component.ts').substitute()
