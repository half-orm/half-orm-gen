from ._helpers import _cname


def _auth_service(version_prefix: str) -> str:
    return f"""\
import {{ Injectable, computed, signal, inject }} from '@angular/core';
import {{ Router }} from '@angular/router';
import {{ Subject }} from 'rxjs';
import {{ clearAllStates, clearStateForKey }} from './state-registry';

export interface WsEvent {{
  event: 'create' | 'update' | 'delete' | 'access_reload';
  resource: string;
  id: unknown;
}}

export interface HoUser {{
  id: string;
  name: string;
  is_admin: boolean;
}}

@Injectable({{ providedIn: 'root' }})
export class AuthService {{
  private router = inject(Router);

  readonly token    = signal<string | null>(
    typeof sessionStorage !== 'undefined' ? sessionStorage.getItem('ho_token') : null
  );
  readonly access               = signal<Record<string, any>>({{}});
  readonly roles                = signal<string[]>([]);
  readonly users                = signal<HoUser[]>([]);
  readonly hasAdmin             = signal<boolean | null>(null);
  readonly accessVersion        = signal<number>(0);
  readonly resourceAccessVersion = signal<Record<string, number>>({{}});
  readonly wsEvent$             = new Subject<WsEvent>();
  readonly fetchedRoutes        = new Set<string>();

  readonly userId = computed<string | null>(() => {{
    const t = this.token();
    if (!t) return null;
    try {{ return (JSON.parse(atob(t.split('.')[1].replace(/-/g,'+').replace(/_/g,'/'))) as any)['sub'] ?? null; }}
    catch {{ return null; }}
  }});

  readonly displayName = computed(() => {{
    const id = this.userId();
    if (!id) return 'anonymous';
    return this.users().find(u => u.id === id)?.name ?? 'anonymous';
  }});

  readonly isAdmin = computed(() => {{
    const id = this.userId();
    return !!id && this.users().some(u => u.id === id && u.is_admin);
  }});

  readonly userRoles = computed<string[]>(() => {{
    const t = this.token();
    if (!t) return [];
    try {{ return (JSON.parse(atob(t.split('.')[1].replace(/-/g,'+').replace(/_/g,'/'))) as any)['roles'] ?? []; }}
    catch {{ return []; }}
  }});

  setToken(jwt: string): void {{
    sessionStorage.setItem('ho_token', jwt);
    this.token.set(jwt);
    this.fetchedRoutes.clear();
    clearAllStates();
    void this._fetchAccess();
    void this._fetchRoles();
    void this._fetchUsers();
  }}

  logout(): void {{
    sessionStorage.removeItem('ho_token');
    this.token.set(null);
    this.fetchedRoutes.clear();
    clearAllStates();
    if (this.router.url.includes('f_')) {{
      void this.router.navigate([this.router.url.split('?')[0]], {{ queryParams: {{}} }});
    }}
    void this._fetchAccess();
    void this._fetchRoles();
  }}

  async loginWithEmail(email: string): Promise<void> {{
    const res = await fetch('{version_prefix}/auth/login', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ email }}),
    }});
    if (!res.ok) throw new Error((await res.json() as any).detail ?? 'Login failed');
    this.setToken(((await res.json()) as any).token);
  }}

  async signupUser(name: string, email: string): Promise<void> {{
    const res = await fetch('{version_prefix}/auth/signup', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ name, email }}),
    }});
    if (!res.ok) throw new Error((await res.json() as any).detail ?? 'Signup failed');
    this.setToken(((await res.json()) as any).token);
  }}

  async _fetchAccess(): Promise<void> {{
    const hdrs: Record<string, string> = this.token()
      ? {{ Authorization: `Bearer ${{this.token()}}` }}
      : {{}};
    try {{
      const res = await fetch('{version_prefix}/ho_access', {{ headers: hdrs }});
      this.access.set(res.ok ? await res.json() : {{}});
    }} catch {{ this.access.set({{}}); }}
  }}

  async _fetchRoles(): Promise<void> {{
    try {{
      const res = await fetch('{version_prefix}/ho_roles');
      if (res.ok) this.roles.set(await res.json());
    }} catch {{}}
  }}

  async _fetchUsers(): Promise<void> {{
    try {{
      const res = await fetch('{version_prefix}/ho_users');
      if (res.ok) this.users.set(await res.json());
    }} catch {{}}
  }}

  async _fetchSetupStatus(): Promise<void> {{
    try {{
      const res = await fetch('{version_prefix}/ho_setup');
      if (res.ok) this.hasAdmin.set(((await res.json()) as any).has_admin);
    }} catch {{}}
  }}

  async _reloadAccess(resource?: string): Promise<void> {{
    if (resource) {{
      for (const url of [...this.fetchedRoutes]) {{
        if (url.includes(`/${{resource}}`)) this.fetchedRoutes.delete(url);
      }}
      clearStateForKey(resource);
      await this._fetchAccess();
      this.resourceAccessVersion.update(v => ({{ ...v, [resource]: (v[resource] ?? 0) + 1 }}));
    }} else {{
      this.fetchedRoutes.clear();
      clearAllStates();
      await Promise.all([this._fetchAccess(), this._fetchRoles()]);
      this.accessVersion.update(v => v + 1);
    }}
  }}

  connectWs(): void {{
    const proto = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss' : 'ws';
    const host  = typeof window !== 'undefined' ? window.location.host : 'localhost:8000';
    const ws = new WebSocket(`${{proto}}://${{host}}{version_prefix}/ws`);
    ws.onmessage = (e) => {{
      try {{
        const msg = JSON.parse(e.data) as WsEvent;
        if (msg.event === 'access_reload') {{ void this._reloadAccess((msg as any).resource); }}
        else {{ this.wsEvent$.next(msg); }}
      }} catch {{}}
    }};
    ws.onclose = () => {{ setTimeout(() => this.connectWs(), 2000); }};
    ws.onerror  = () => ws.close();
  }}
}}
"""


def _app_component(resources: list, version_prefix: str = '') -> str:
    api_base = version_prefix or '/api'
    return f"""\
import {{ Component, computed, inject, OnInit, signal }} from '@angular/core';
import {{ RouterLink, RouterLinkActive, RouterOutlet, NavigationEnd, Router }} from '@angular/router';
import {{ takeUntilDestroyed }} from '@angular/core/rxjs-interop';
import {{ filter }} from 'rxjs';
import {{ AuthService }} from './core/auth.service';
import {{ SiloRegistry }} from './generated/silo-registry.service';

const API_BASE = '{api_base}';

@Component({{
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <div class="h-screen flex flex-col bg-gray-50 overflow-hidden" (click)="closeMenu($event)">
      @if (!isHome()) {{
        <header class="shrink-0 bg-white border-b h-11 flex items-center justify-between px-4">
          <span class="font-bold text-gray-800">halfORM Backoffice</span>
          <div class="relative">
            <button (click)="menuOpen = !menuOpen; $event.stopPropagation()"
                    [class]="'flex items-center gap-1 text-xs px-3 py-1 rounded-full border transition-colors ' +
                             (auth.token() ? 'border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100'
                                          : 'border-gray-300 text-gray-500 hover:bg-gray-50')">
              {{{{ auth.displayName() }}}}
              <span class="opacity-60">{{{{ menuOpen ? '▲' : '▼' }}}}</span>
            </button>
            @if (menuOpen) {{
              <div class="absolute right-0 top-full mt-1 bg-white border rounded-lg shadow-lg z-50 w-64 p-3"
                   (click)="$event.stopPropagation()">
                @if (auth.token()) {{
                  <p class="text-xs text-gray-500 mb-2">Signed in as <strong>{{{{ auth.displayName() }}}}</strong></p>
                  <button (click)="logout()"
                          class="w-full text-left px-2 py-1.5 text-xs text-red-500 hover:bg-red-50 rounded transition-colors">
                    Sign out
                  </button>
                }} @else if (auth.hasAdmin() === false) {{
                  <p class="text-xs font-semibold text-gray-700 mb-3">Create admin account</p>
                  <input (input)="signupName.set($any($event).target.value)"
                         [value]="signupName()" placeholder="Name"
                         class="w-full text-xs border rounded px-2 py-1.5 mb-2 focus:outline-none focus:ring-1 focus:ring-blue-400"/>
                  <input (input)="signupEmail.set($any($event).target.value)"
                         [value]="signupEmail()" placeholder="Email" type="email"
                         class="w-full text-xs border rounded px-2 py-1.5 mb-2 focus:outline-none focus:ring-1 focus:ring-blue-400"/>
                  @if (authError()) {{
                    <p class="text-xs text-red-500 mb-1">{{{{ authError() }}}}</p>
                  }}
                  <button (click)="doSignup()"
                          class="w-full text-xs bg-blue-600 text-white px-2 py-1.5 rounded hover:bg-blue-700 transition-colors">
                    Create account
                  </button>
                }} @else {{
                  @if (!showSignup()) {{
                    <p class="text-xs font-semibold text-gray-700 mb-3">Sign in</p>
                    <input (input)="loginEmail.set($any($event).target.value)"
                           [value]="loginEmail()" placeholder="Email" type="email"
                           (keydown.enter)="doLogin()"
                           class="w-full text-xs border rounded px-2 py-1.5 mb-2 focus:outline-none focus:ring-1 focus:ring-blue-400"/>
                    @if (authError()) {{
                      <p class="text-xs text-red-500 mb-1">{{{{ authError() }}}}</p>
                    }}
                    <button (click)="doLogin()"
                            class="w-full text-xs bg-blue-600 text-white px-2 py-1.5 rounded hover:bg-blue-700 transition-colors mb-2">
                      Sign in
                    </button>
                    <button (click)="showSignup.set(true); authError.set('')"
                            class="w-full text-xs text-blue-500 hover:underline">
                      Create account
                    </button>
                  }} @else {{
                    <p class="text-xs font-semibold text-gray-700 mb-3">Create account</p>
                    <input (input)="signupName.set($any($event).target.value)"
                           [value]="signupName()" placeholder="Name"
                           class="w-full text-xs border rounded px-2 py-1.5 mb-2 focus:outline-none focus:ring-1 focus:ring-blue-400"/>
                    <input (input)="signupEmail.set($any($event).target.value)"
                           [value]="signupEmail()" placeholder="Email" type="email"
                           class="w-full text-xs border rounded px-2 py-1.5 mb-2 focus:outline-none focus:ring-1 focus:ring-blue-400"/>
                    @if (authError()) {{
                      <p class="text-xs text-red-500 mb-1">{{{{ authError() }}}}</p>
                    }}
                    <button (click)="doSignup()"
                            class="w-full text-xs bg-blue-600 text-white px-2 py-1.5 rounded hover:bg-blue-700 transition-colors mb-2">
                      Create account
                    </button>
                    <button (click)="showSignup.set(false); authError.set('')"
                            class="w-full text-xs text-gray-400 hover:underline">
                      Back to sign in
                    </button>
                  }}
                }}
              </div>
            }}
          </div>
        </header>
        <div class="flex flex-1 overflow-hidden">
          <aside class="w-max shrink-0 bg-white border-r flex flex-col">
            <div class="px-2 pt-2 pb-1">
              <input [value]="navFilter()" (input)="navFilter.set($any($event).target.value)"
                     placeholder="Filter…"
                     class="w-full text-xs border rounded px-2 py-1 text-gray-700"/>
            </div>
            <nav class="flex-1 overflow-y-auto px-2 py-2 space-y-0.5">
              @for (item of filteredNav(); track item.href) {{
                <a [routerLink]="item.href" routerLinkActive="bg-gray-100 font-semibold"
                   class="block px-3 py-2 rounded hover:bg-gray-100 text-sm text-gray-700">
                  {{{{ item.label }}}}
                </a>
              }}
            </nav>
            <div class="px-4 py-3 border-t flex items-center justify-between">
              @if (auth.isAdmin()) {{
                <a routerLink="/ho_bo/admin" routerLinkActive="text-blue-600"
                   class="text-gray-400 hover:text-blue-600 transition-colors text-xs font-medium" title="Admin">⚙</a>
              }}
              <a routerLink="/schema" routerLinkActive="text-blue-600"
                 class="text-gray-400 hover:text-blue-600 transition-colors" title="Schema">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="w-6 h-6">
                  <path d="M21 6.375c0 2.692-4.03 4.875-9 4.875S3 9.067 3 6.375 7.03 1.5 12 1.5s9 2.183 9 4.875z" />
                  <path d="M12 12.75c2.685 0 5.19-.586 7.078-1.609a8.283 8.283 0 001.897-1.384c.016.121.025.244.025.368C21 12.817 16.97 15 12 15s-9-2.183-9-4.875c0-.124.009-.247.025-.368a8.285 8.285 0 001.897 1.384C6.809 12.164 9.315 12.75 12 12.75z" />
                  <path d="M12 16.5c2.685 0 5.19-.586 7.078-1.609a8.282 8.282 0 001.897-1.384c.016.121.025.244.025.368 0 2.692-4.03 4.875-9 4.875s-9-2.183-9-4.875c0-.124.009-.247.025-.368a8.284 8.284 0 001.897 1.384C6.809 15.914 9.315 16.5 12 16.5z" />
                </svg>
              </a>
            </div>
          </aside>
          <main class="flex-1 overflow-y-auto p-6">
            <router-outlet />
          </main>
        </div>
      }}
      @else {{
        <main class="flex-1 overflow-y-auto">
          <router-outlet />
        </main>
      }}
    </div>
  `
}})
export class AppComponent implements OnInit {{
  protected auth     = inject(AuthService);
  protected registry = inject(SiloRegistry);
  private   router   = inject(Router);

  readonly isHome = signal(this.router.url === '/');
  navFilter  = signal('');
  menuOpen   = false;
  showSignup = signal(false);
  loginEmail = signal('');
  signupName = signal('');
  signupEmail = signal('');
  authError  = signal('');

  readonly navItems = computed(() =>
    Object.keys(this.registry.meta())
      .map(key => ({{ href: `/ho_bo/${{key}}`, label: key.replace('/', '.') }}))
      .sort((a, b) => a.label.localeCompare(b.label))
  );

  readonly filteredNav = computed(() => {{
    const q = this.navFilter().toLowerCase();
    return q ? this.navItems().filter(i => i.label.toLowerCase().includes(q)) : this.navItems();
  }});

  constructor() {{
    this.router.events.pipe(
      filter(e => e instanceof NavigationEnd),
      takeUntilDestroyed(),
    ).subscribe(e => this.isHome.set((e as NavigationEnd).urlAfterRedirects === '/'));
  }}

  ngOnInit(): void {{
    this.menuOpen = !this.auth.token();
    void this.registry.init(API_BASE);
    void this.auth._fetchAccess();
    void this.auth._fetchRoles();
    void this.auth._fetchUsers();
    void this.auth._fetchSetupStatus();
    this.auth.connectWs();
  }}

  async doLogin(): Promise<void> {{
    this.authError.set('');
    try {{
      await this.auth.loginWithEmail(this.loginEmail());
      this.menuOpen = false;
      this.loginEmail.set('');
    }} catch (e: any) {{
      this.authError.set(e.message ?? 'Login failed');
    }}
  }}

  async doSignup(): Promise<void> {{
    this.authError.set('');
    try {{
      await this.auth.signupUser(this.signupName(), this.signupEmail());
      this.menuOpen = false;
      this.signupName.set(''); this.signupEmail.set('');
    }} catch (e: any) {{
      this.authError.set(e.message ?? 'Signup failed');
    }}
  }}

  logout(): void {{
    this.auth.logout();
    this.menuOpen = true;
    this.showSignup.set(false);
    void this.router.navigate(['/']);
  }}

  closeMenu(e: MouseEvent): void {{
    if (this.menuOpen && !(e.target as HTMLElement).closest('.relative')) {{
      this.menuOpen = false;
    }}
  }}
}}
"""


def _auth_guard_ts() -> str:
    return """\
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from './auth.service';

export function authGuard(): boolean {
  const auth   = inject(AuthService);
  const router = inject(Router);
  if (auth.token()) return true;
  void router.navigate(['/login']);
  return false;
}
"""


def _admin_guard_ts() -> str:
    return """\
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from './auth.service';

export async function adminGuard(): Promise<boolean> {
  const auth  = inject(AuthService);
  const router = inject(Router);
  if (auth.token() && auth.users().length === 0) {
    await auth._fetchUsers();
  }
  if (auth.isAdmin()) return true;
  void router.navigate(['/ho_bo']);
  return false;
}
"""


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
    if include_admin:
        lines.append(
            "  { path: 'ho_bo/admin', loadComponent: () => import('./generated/ho_admin/ho_admin.component').then(m => m.HoAdminComponent), canActivate: [adminGuard] },"
        )
    for sn, tn, _, has_post, _, pk_info, *__ in resources:
        cn   = _cname(sn, tn)
        stem = f'{sn}_{tn}'
        base = f'./generated/components/{stem}'
        lines.append(
            f"  {{ path: 'ho_bo/{sn}/{tn}', loadComponent: () => import('{base}/list.component').then(m => m.{cn}ListComponent) }},"
        )
        if has_post:
            lines.append(
                f"  {{ path: 'ho_bo/{sn}/{tn}/new', loadComponent: () => import('{base}/create.component').then(m => m.{cn}CreateComponent) }},"
            )
        if pk_info:
            lines.append(
                f"  {{ path: 'ho_bo/{sn}/{tn}/:id', loadComponent: () => import('{base}/detail.component').then(m => m.{cn}DetailComponent) }},"
            )
    lines += ['];', '']
    return '\n'.join(lines)


def _login_component(version_prefix: str) -> str:
    return """\
import { Component, inject } from '@angular/core';
import { AuthService } from '../../core/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  template: `
    <div class="flex flex-col items-center justify-center h-full text-gray-400 text-sm gap-2">
      @if (auth.token()) {
        <p>Logged in as <span class="font-semibold text-gray-700">{{ auth.displayName() }}</span></p>
        <p>Select a resource from the sidebar.</p>
      } @else {
        <p>Sign in using the button in the top right corner.</p>
      }
    </div>
  `
})
export class LoginComponent {
  protected auth = inject(AuthService);
}
"""


def _access_component(version_prefix: str) -> str:
    return f"""\
import {{ Component, computed, inject }} from '@angular/core';
import {{ AuthService }} from '../../core/auth.service';

const VERB_COLOR: Record<string, string> = {{
  GET:    'bg-blue-100 text-blue-700',
  POST:   'bg-green-100 text-green-700',
  PUT:    'bg-yellow-100 text-yellow-700',
  DELETE: 'bg-red-100 text-red-700',
}};

@Component({{
  selector: 'app-access',
  standalone: true,
  template: `
    <div class="flex h-full gap-6">
      <div class="w-44 shrink-0">
        <h2 class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Roles</h2>
        @if (rolesLoading()) {{
          <p class="text-gray-400 text-sm">Loading…</p>
        }} @else {{
          <div class="space-y-1">
            @for (role of roles(); track role) {{
              <div class="w-full text-left px-3 py-2 rounded text-sm"
                   [class]="auth.userRoles().includes(role)
                     ? 'bg-blue-100 text-blue-700 font-semibold'
                     : 'text-gray-700'">
                {{{{ role }}}}
              </div>
            }}
          </div>
        }}
      </div>

      <div class="flex-1 min-w-0">
        <h1 class="text-2xl font-bold mb-6">
          Authorizations
          <span class="text-base font-normal text-gray-500">— {{{{ activeRole() }}}}</span>
        </h1>
        @if (accessEntries().length === 0) {{
          <p class="text-gray-500 text-sm">No access granted for this role.</p>
        }} @else {{
          <div class="space-y-4">
            @for (entry of accessEntries(); track entry[0]) {{
              <div class="bg-white rounded-lg shadow-sm overflow-hidden">
                <div class="px-4 py-2 bg-gray-100 font-semibold text-gray-700 text-sm">
                  {{{{ entry[0] }}}}
                </div>
                <div class="divide-y">
                  @for (verb of objectEntries(entry[1]); track verb[0]) {{
                    <div class="px-4 py-3 flex gap-4 items-start text-sm">
                      <span class="inline-block px-2 py-0.5 rounded font-mono text-xs font-bold w-16 text-center"
                            [class]="verbColor(verb[0])">
                        {{{{ verb[0] }}}}
                      </span>
                      <div class="text-gray-700">
                        @if (verb[0] === 'DELETE') {{
                          <span class="text-green-600">allowed</span>
                        }} @else if (verb[0] === 'GET') {{
                          <span class="text-gray-400">out: </span>{{{{ asGet(verb[1]).join(', ') }}}}
                        }} @else {{
                          <div><span class="text-gray-400">in:  </span>{{{{ asInOut(verb[1]).in.join(', ') }}}}</div>
                          <div><span class="text-gray-400">out: </span>{{{{ asInOut(verb[1]).out.join(', ') }}}}</div>
                        }}
                      </div>
                    </div>
                  }}
                </div>
              </div>
            }}
          </div>
        }}
      </div>
    </div>
  `
}})
export class AccessComponent {{
  protected auth = inject(AuthService);

  readonly roles         = this.auth.roles;
  readonly rolesLoading  = computed(() => this.auth.roles().length === 0);
  readonly activeRole    = computed(() => this.auth.userRoles()[0] ?? 'anonymous');
  readonly accessEntries = computed(() => Object.entries(this.auth.access()));

  objectEntries(obj: any): [string, any][] {{ return Object.entries(obj ?? {{}}); }}
  verbColor(verb: string): string {{ return VERB_COLOR[verb] ?? 'bg-gray-100 text-gray-600'; }}
  asGet(v: any): string[]               {{ return v?.out ?? []; }}
  asInOut(v: any): {{in: string[]; out: string[]}} {{ return {{ in: v?.in ?? [], out: v?.out ?? [] }}; }}
}}
"""
