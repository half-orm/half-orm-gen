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
    _py_type_str,
)
from half_orm_gen.gen_store.base import StoreGenerator


# ---------------------------------------------------------------------------
# Naming helpers
# ---------------------------------------------------------------------------

def _cname(schema_name: str, table_name: str) -> str:
    """PascalCase — BlogAuthor"""
    schema_name = schema_name.replace('.', '_')
    return ''.join(p.capitalize() for p in f'{schema_name}_{table_name}'.split('_'))


def _selector(schema_name: str, table_name: str, suffix: str) -> str:
    """app-blog-author-list"""
    schema_name = schema_name.replace('.', '_')
    slug = f'{schema_name}_{table_name}'.replace('_', '-')
    return f'app-{slug}-{suffix}'


def _title(schema_name: str, table_name: str) -> str:
    return f'{schema_name}.{table_name}'


def _field_type_category(field_obj) -> str:
    """Map Python type to validation category: date, datetime, number, or string."""
    py_type = _py_type_str(field_obj.py_type)
    if py_type == 'datetime.date':
        return 'date'
    if py_type == 'datetime.datetime':
        return 'datetime'
    if py_type in ('int', 'float', 'decimal.Decimal'):
        return 'number'
    return 'string'


def _store_import_path(schema_name: str, table_name: str, depth: int) -> str:
    prefix = '../' * depth
    return f"{prefix}stores/{schema_name}_{table_name}.store"


def _core_path(depth: int) -> str:
    return '../' * depth + 'core'


# ---------------------------------------------------------------------------
# Static file templates
# ---------------------------------------------------------------------------

_PACKAGE_JSON = """\
{{
  "name": "{project_name}",
  "version": "0.0.1",
  "private": true,
  "scripts": {{
    "start": "ng serve",
    "build": "ng build",
    "watch": "ng build --watch --configuration development"
  }},
  "dependencies": {{
    "@angular/animations": "^22.0.0",
    "@angular/common": "^22.0.0",
    "@angular/compiler": "^22.0.0",
    "@angular/core": "^22.0.0",
    "@angular/forms": "^22.0.0",
    "@angular/platform-browser": "^22.0.0",
    "@angular/platform-browser-dynamic": "^22.0.0",
    "@angular/router": "^22.0.0",
    "katex": "^0.16.0",
    "rxjs": "~7.8.0",
    "tslib": "^2.3.0",
    "zone.js": "~0.15.0"
  }},
  "devDependencies": {{
    "@angular/build": "^22.0.0",
    "@angular/cli": "^22.0.0",
    "@angular/compiler-cli": "^22.0.0",
    "@types/katex": "^0.16.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0",
    "tailwindcss": "^3.4.0",
    "typescript": "~6.0.0"
  }}
}}
"""

_ANGULAR_JSON = """\
{{
  "$schema": "./node_modules/@angular/cli/lib/config/schema.json",
  "version": 1,
  "projects": {{
    "{project_name}": {{
      "projectType": "application",
      "root": "",
      "sourceRoot": "src",
      "architect": {{
        "build": {{
          "builder": "@angular/build:application",
          "options": {{
            "outputPath": "dist/{project_name}",
            "index": "src/index.html",
            "browser": "src/main.ts",
            "polyfills": ["zone.js"],
            "tsConfig": "tsconfig.app.json",
            "assets": [{{"glob": "**/*", "input": "public"}}],
            "styles": ["src/styles.css"],
            "scripts": []
          }},
          "configurations": {{
            "production": {{
              "budgets": [
                {{"type": "initial", "maximumWarning": "500kB", "maximumError": "1MB"}},
                {{"type": "anyComponentStyle", "maximumWarning": "4kB", "maximumError": "8kB"}}
              ],
              "outputHashing": "all"
            }},
            "development": {{
              "optimization": false,
              "extractLicenses": false,
              "sourceMap": true
            }}
          }},
          "defaultConfiguration": "production"
        }},
        "serve": {{
          "builder": "@angular/build:dev-server",
          "configurations": {{
            "production": {{"buildTarget": "{project_name}:build:production"}},
            "development": {{
              "buildTarget": "{project_name}:build:development",
              "proxyConfig": "proxy.conf.json"
            }}
          }},
          "defaultConfiguration": "development"
        }}
      }}
    }}
  }}
}}
"""

_TSCONFIG = """\
{
  "compileOnSave": false,
  "compilerOptions": {
    "outDir": "./dist/out-tsc",
    "strict": true,
    "noImplicitOverride": true,
    "noPropertyAccessFromIndexSignature": true,
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true,
    "skipLibCheck": true,
    "isolatedModules": true,
    "esModuleInterop": true,
    "moduleResolution": "bundler",
    "importHelpers": true,
    "target": "ES2022",
    "module": "ES2022",
    "lib": ["ES2022", "dom"]
  },
  "angularCompilerOptions": {
    "enableI18nLegacyMessageIdFormat": false,
    "strictInjectionParameters": true,
    "strictInputAccessModifiers": true,
    "strictTemplates": true
  }
}
"""

_TSCONFIG_APP = """\
{
  "extends": "./tsconfig.json",
  "compilerOptions": {
    "outDir": "./out-tsc/app",
    "types": []
  },
  "files": ["src/main.ts"],
  "include": ["src/**/*.d.ts"]
}
"""

_INDEX_HTML = """\
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{project_title}</title>
  <base href="/">
  <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body>
  <app-root></app-root>
</body>
</html>
"""

_STYLES_CSS = """\
@import 'katex/dist/katex.min.css';
@tailwind base;
@tailwind components;
@tailwind utilities;
"""

_LATEX_PIPE = """\
import { Pipe, PipeTransform, inject } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import katex from 'katex';

@Pipe({ name: 'latex', standalone: true })
export class LatexPipe implements PipeTransform {
    private sanitizer = inject(DomSanitizer);

    transform(value: unknown): SafeHtml {
        const text = String(value ?? '');
        if (!text || (!text.includes('$') && !text.includes('\\\\(')))
            return this.escHtml(text);
        return this.sanitizer.bypassSecurityTrustHtml(this.renderMath(text));
    }

    private renderMath(text: string): string {
        const parts = text.split(/(\\$\\$[\\s\\S]+?\\$\\$|\\$[^$\\n]+?\\$)/g);
        return parts.map((part, i) => {
            if (i % 2 === 0) return this.escHtml(part);
            const display = part.startsWith('$$');
            const math = display ? part.slice(2, -2) : part.slice(1, -1);
            return katex.renderToString(math, { displayMode: display, throwOnError: false });
        }).join('');
    }

    private escHtml(s: string): string {
        return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
                .replace(/\\n/g, '<br>');
    }
}
"""

_TAILWIND_CONFIG = """\
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{html,ts}'],
  theme: { extend: {} },
  plugins: []
};
"""

_POSTCSS_CONFIG = """\
module.exports = {
  plugins: { tailwindcss: {}, autoprefixer: {} }
};
"""

_MAIN_TS = """\
import { bootstrapApplication } from '@angular/platform-browser';
import { appConfig } from './app/app.config';
import { AppComponent } from './app/app.component';

bootstrapApplication(AppComponent, appConfig)
  .catch(err => console.error(err));
"""

_APP_CONFIG_TS = """\
import { ApplicationConfig, provideZoneChangeDetection } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes),
    provideHttpClient(),
  ]
};
"""

_STATE_REGISTRY = """\
const _fns: Array<() => void> = [];
export function registerClear(fn: () => void): void { _fns.push(fn); }
export function clearAllStates(): void { _fns.forEach(fn => fn()); }
"""


# ---------------------------------------------------------------------------
# Dynamic templates
# ---------------------------------------------------------------------------

def _proxy_conf(version_prefix: str) -> str:
    prefix = version_prefix or '/api'
    return (
        '{\n'
        f'  "{prefix}": {{\n'
        '    "target": "http://localhost:8000",\n'
        '    "secure": false,\n'
        '    "ws": true\n'
        '  }\n'
        '}\n'
    )


def _auth_service(version_prefix: str) -> str:
    return f"""\
import {{ Injectable, signal, inject }} from '@angular/core';
import {{ Router }} from '@angular/router';
import {{ Subject }} from 'rxjs';
import {{ clearAllStates }} from './state-registry';

export interface WsEvent {{
  event: 'create' | 'update' | 'delete';
  resource: string;
  id: unknown;
}}

@Injectable({{ providedIn: 'root' }})
export class AuthService {{
  private router = inject(Router);
  readonly token      = signal<string | null>(
    typeof sessionStorage !== 'undefined' ? sessionStorage.getItem('ho_token') : null
  );
  readonly access     = signal<Record<string, any>>({{}});
  readonly wsEvent$   = new Subject<WsEvent>();
  readonly fetchedRoutes = new Set<string>();

  login(t: string): void {{
    sessionStorage.setItem('ho_token', t);
    this.token.set(t);
    this.fetchedRoutes.clear();
    clearAllStates();
    void this._fetchAccess();
  }}

  logout(): void {{
    sessionStorage.removeItem('ho_token');
    this.token.set(null);
    this.fetchedRoutes.clear();
    clearAllStates();

    // Clear filter query params on logout
    if (this.router.url.includes('f_')) {{
      const currentUrl = this.router.url.split('?')[0];
      void this.router.navigate([currentUrl], {{ queryParams: {{}} }});
    }}

    void this._fetchAccess();
  }}

  async _fetchAccess(): Promise<void> {{
    const hdrs: Record<string, string> = this.token()
      ? {{ Authorization: `Bearer ${{this.token()}}` }}
      : {{}};
    try {{
      const res = await fetch('{version_prefix}/ho_access', {{ headers: hdrs }});
      this.access.set(res.ok ? await res.json() : {{}});
    }} catch {{
      this.access.set({{}});
    }}
  }}

  connectWs(): void {{
    const proto = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss' : 'ws';
    const host  = typeof window !== 'undefined' ? window.location.host : 'localhost:8000';
    const ws = new WebSocket(`${{proto}}://${{host}}{version_prefix}/ws`);
    ws.onmessage = (e) => {{
      try {{ this.wsEvent$.next(JSON.parse(e.data) as WsEvent); }} catch {{}}
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
              {{{{ auth.token() ?? 'anonymous' }}}}
              <span class="opacity-60">{{{{ menuOpen ? '▲' : '▼' }}}}</span>
            </button>
            @if (menuOpen) {{
              <div class="absolute right-0 top-full mt-1 bg-white border rounded-lg shadow-lg z-50 min-w-44 py-1">
                @if (roles().length === 0) {{
                  <p class="px-4 py-2 text-xs text-gray-400">Loading…</p>
                }} @else {{
                  @for (role of roles(); track role) {{
                    <button (click)="selectRole(role)"
                            [class]="'w-full text-left px-4 py-2 text-xs hover:bg-blue-50 transition-colors ' +
                                     (auth.token() === role ? 'font-semibold text-blue-600' : 'text-gray-700')">
                      {{{{ role }}}}
                    </button>
                  }}
                }}
                <div class="mx-3 my-1 border-t border-dashed border-orange-200"></div>
                <button (click)="selectRole('ho_dev')"
                        [class]="'w-full text-left px-4 py-2 text-xs text-orange-600 hover:bg-orange-50 transition-colors ' +
                                 (auth.token() === 'ho_dev' ? 'font-semibold' : '')">
                  ho_dev <span class="opacity-60 text-xs">(dev)</span>
                </button>
                @if (auth.token()) {{
                  <div class="mx-3 my-1 border-t border-gray-100"></div>
                  <button (click)="logout()"
                          class="w-full text-left px-4 py-2 text-xs text-gray-400 hover:bg-gray-50 transition-colors">
                    Sign out
                  </button>
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
              <a routerLink="/">
                <img src="/logo.png" alt="halfORM" class="h-10 w-auto opacity-80 hover:opacity-100 transition-opacity" />
              </a>
              <a routerLink="/schema" routerLinkActive="opacity-100 text-blue-600"
                 class="opacity-50 hover:opacity-100 transition-opacity text-gray-600" title="Schema">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="h-6 w-6">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 5.625c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125" />
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

  readonly isHome   = signal(this.router.url === '/');
  navFilter = signal('');
  menuOpen  = false;
  readonly roles = signal<string[]>([]);

  readonly navItems = computed(() =>
    Object.keys(this.registry.meta())
      .map(key => ({{ href: `/ho_bo/${{key}}`, label: key.replace('/', '.') }}))
      .sort((a, b) => a.label.localeCompare(b.label))
  );

  readonly filteredNav = computed(() => {{
    const q = this.navFilter().toLowerCase();
    return q
      ? this.navItems().filter(i => i.label.toLowerCase().includes(q))
      : this.navItems();
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
    this.auth.connectWs();
    fetch(`${{API_BASE}}/ho_roles`)
      .then(r => r.ok ? r.json() : [])
      .then((d: string[]) => this.roles.set(d));
  }}

  selectRole(role: string): void {{
    this.auth.login(role);
    this.menuOpen = false;
  }}

  logout(): void {{
    this.auth.logout();
    this.menuOpen = true;
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


def _home_component_ts(first_route: str) -> str:
    return f"""\
import {{ Component }} from '@angular/core';
import {{ RouterLink }} from '@angular/router';

@Component({{
  selector: 'app-home',
  standalone: true,
  imports: [RouterLink],
  template: `
    <div class="flex flex-col items-center justify-center h-full bg-gray-50 py-16">
      <div class="flex items-center gap-6 mb-6">
        <img src="logo.png" alt="halfORM" class="h-30 w-auto" />
      </div>
      <h1 class="text-3xl font-bold text-gray-800 mb-2">halfORM Backoffice</h1>
      <p class="text-gray-500">Powered by Angular
      </p>
      <div class="mb-8">
        <img src="angular_200x200.png" alt="Angular" class="h-10 w-auto" />
      </div>
      <a [routerLink]="['/ho_bo']"
         class="bg-red-600 text-white px-6 py-3 rounded-lg hover:bg-red-700 font-medium transition-colors">
        Open Backoffice →
      </a>
    </div>
  `
}})
export class HomeComponent {{}}
"""


def _schema_component_ts() -> str:
    return """\
import { Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { SiloRegistry } from '../../generated/silo-registry.service';
import { FieldSchema, FkDep } from '../../generated/schema.types';

interface ResourceView {
  key: string;
  table: string;
  kind: string;
  fields: (FieldSchema & { fkTarget: string | null })[];
  reverseFks: string[];
}

@Component({
  selector: 'app-schema',
  standalone: true,
  imports: [RouterLink],
  styles: [':host { display: flex; height: 100%; overflow: hidden; }'],
  template: `
    <aside class="w-max shrink-0 overflow-y-auto border-r bg-white flex flex-col">
      <div class="px-3 pt-3 pb-2 border-b">
        <input [value]="tocFilter()" (input)="tocFilter.set($any($event).target.value)"
               placeholder="Filter…"
               class="w-full text-xs border rounded px-2 py-1 text-gray-700"/>
      </div>
      <div class="px-3 py-3 space-y-4 flex-1">
        @for (schema of filteredSchemas(); track schema.name) {
          <div>
            <a (click)="scrollTo('s__' + schema.name)"
               class="block text-xs font-semibold text-gray-500 uppercase tracking-wide hover:text-gray-800 cursor-pointer mb-1">
              {{ schema.name }}
            </a>
            <ul class="space-y-0.5 pl-2">
              @for (res of schema.resources; track res.key) {
                <li>
                  <a (click)="scrollTo(res.key.replace('/', '_'))"
                     class="text-sm text-blue-600 hover:underline cursor-pointer">{{ res.table }}</a>
                </li>
              }
            </ul>
          </div>
        }
      </div>
    </aside>

    <div class="flex-1 overflow-y-auto px-6 py-6 space-y-10">
      <h1 class="text-2xl font-bold text-gray-800">Database Schema</h1>
      @for (schema of schemas(); track schema.name) {
        <section [id]="'s__' + schema.name">
          <h2 class="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-3 border-b pb-1">
            {{ schema.name }}
          </h2>
          <div class="space-y-4">
            @for (res of schema.resources; track res.key) {
              <div class="bg-white border rounded-lg overflow-hidden" [id]="res.key.replace('/', '_')">
                <div class="flex items-center gap-2 px-4 py-2 bg-gray-50 border-b">
                  <a [routerLink]="['/ho_bo', res.key]"
                     class="font-semibold text-blue-700 hover:underline">{{ res.table }}</a>
                  <span class="text-xs text-gray-400 border rounded px-1">{{ res.kind }}</span>
                </div>
                <table class="w-full text-sm">
                  @for (field of res.fields; track field.name) {
                    <tr class="border-b last:border-b-0 hover:bg-gray-50">
                      <td class="px-4 py-1.5 font-mono text-xs w-1/3"
                          [class.font-bold]="field.is_pk"
                          [class.text-amber-700]="field.is_pk">
                        {{ field.is_pk ? '[PK] ' : '' }}{{ field.name }}
                      </td>
                      <td class="px-4 py-1.5 text-gray-500 text-xs w-1/4">{{ field.sql_type }}</td>
                      <td class="px-4 py-1.5 text-xs">
                        @if (field.fkTarget) {
                          <a (click)="scrollTo(field.fkTarget!.replace('/', '_'))"
                             class="text-blue-600 hover:underline cursor-pointer">&rightarrow; {{ field.fkTarget }}</a>
                        }
                      </td>
                    </tr>
                  }
                  @if (res.reverseFks.length > 0) {
                    <tr class="bg-gray-50 border-b">
                      <td colspan="3" class="px-4 py-1 text-xs font-semibold text-gray-400 uppercase tracking-wide">
                        Referenced by
                      </td>
                    </tr>
                    @for (rfk of res.reverseFks; track rfk) {
                      <tr class="border-b last:border-b-0 hover:bg-gray-50">
                        <td colspan="2"></td>
                        <td class="px-4 py-1.5 text-xs">
                          <a (click)="scrollTo(rfk.replace('/', '_'))"
                             class="text-indigo-500 hover:underline cursor-pointer">&leftarrow; {{ rfk }}</a>
                        </td>
                      </tr>
                    }
                  }
                </table>
              </div>
            }
          </div>
        </section>
      }
    </div>
  `,
})
export class SchemaComponent {
  private registry = inject(SiloRegistry);

  tocFilter = signal('');

  scrollTo(id: string): void {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
  }

  readonly schemas = computed(() => {
    const meta = this.registry.meta();
    const bySchema = new Map<string, ResourceView[]>();
    for (const [key, res] of Object.entries(meta)) {
      if (!bySchema.has(res.schema)) bySchema.set(res.schema, []);
      const fkByField = new Map<string, string>();
      for (const fk of res.fk_deps as FkDep[]) {
        for (const lf of fk.local_fields) {
          fkByField.set(lf, `${fk.remote_schema}/${fk.remote_table}`);
        }
      }
      bySchema.get(res.schema)!.push({
        key,
        table: res.table,
        kind: res.kind,
        fields: (res.fields as FieldSchema[]).map(f => ({
          ...f,
          fkTarget: fkByField.get(f.name) ?? null,
        })),
        reverseFks: (res.reverse_fks as (FkDep & { is_singleton: boolean })[])
          .map(rfk => `${rfk.remote_schema}/${rfk.remote_table}`),
      });
    }
    return [...bySchema.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([name, resources]) => ({
        name,
        resources: resources.sort((a, b) => a.table.localeCompare(b.table)),
      }));
  });

  readonly filteredSchemas = computed(() => {
    const q = this.tocFilter().toLowerCase().trim();
    if (!q) return this.schemas();
    return this.schemas()
      .map(s => ({
        ...s,
        resources: s.name.toLowerCase().includes(q)
          ? s.resources
          : s.resources.filter(r => r.table.toLowerCase().includes(q)),
      }))
      .filter(s => s.resources.length > 0);
  });
}
"""


def _app_routes(resources: list, first_route: str) -> str:
    lines = [
        "import { Routes } from '@angular/router';",
        '',
        'export const routes: Routes = [',
        "  { path: '', loadComponent: () => import('./pages/home/home.component').then(m => m.HomeComponent) },",
        "  { path: 'ho_bo',  loadComponent: () => import('./pages/login/login.component').then(m => m.LoginComponent) },",
        "  { path: 'login',  loadComponent: () => import('./pages/login/login.component').then(m => m.LoginComponent) },",
        "  { path: 'access', loadComponent: () => import('./pages/access/access.component').then(m => m.AccessComponent) },",
        "  { path: 'schema', loadComponent: () => import('./pages/schema/schema.component').then(m => m.SchemaComponent) },",
    ]
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
        <p>Logged in as <span class="font-semibold text-gray-700">{{ auth.token() }}</span></p>
        <p>Select a resource from the sidebar.</p>
      } @else {
        <p>Select a role using the button in the top right corner.</p>
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
import {{ Component, computed, inject, OnInit, signal }} from '@angular/core';
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
              <button (click)="selectRole(role)"
                      class="w-full text-left px-3 py-2 rounded text-sm transition-colors"
                      [class]="activeRole() === role
                        ? 'bg-blue-600 text-white font-semibold'
                        : 'text-gray-700 hover:bg-gray-100'">
                {{{{ role }}}}
              </button>
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
export class AccessComponent implements OnInit {{
  protected auth = inject(AuthService);

  readonly roles        = signal<string[]>([]);
  readonly rolesLoading = signal(true);
  readonly activeRole   = computed(() => this.auth.token() ?? 'anonymous');
  readonly accessEntries = computed(() => Object.entries(this.auth.access()));

  ngOnInit(): void {{
    fetch('{version_prefix}/ho_roles')
      .then(r => r.json())
      .then((d: string[]) => {{ this.roles.set(d); this.rolesLoading.set(false); }});
  }}

  selectRole(role: string): void {{
    if (role === 'anonymous') this.auth.logout();
    else this.auth.login(role);
  }}

  objectEntries(obj: any): [string, any][] {{ return Object.entries(obj ?? {{}}); }}
  verbColor(verb: string): string {{ return VERB_COLOR[verb] ?? 'bg-gray-100 text-gray-600'; }}
  asGet(v: any): string[]               {{ return v?.out ?? []; }}
  asInOut(v: any): {{in: string[]; out: string[]}} {{ return {{ in: v?.in ?? [], out: v?.out ?? [] }}; }}
}}
"""


# ---------------------------------------------------------------------------
# Per-resource store
# ---------------------------------------------------------------------------

def _store(
    schema_name: str, table_name: str, base_path: str,
    iname: str,
    out_names: list, all_fields: dict, pk_field: str | None, pk_ts_type: str, pk_extractor: str | None,
    has_post: bool, has_put: bool, has_del: bool,
    post_in_names: list, put_in_names: list,
) -> str:
    lines = []

    lines.append("import { Injectable, signal } from '@angular/core';")
    lines.append("import { HttpClient, HttpHeaders } from '@angular/common/http';")
    lines.append("import { inject } from '@angular/core';")
    lines.append("import { catchError, filter, of, tap } from 'rxjs';")
    lines.append("import { AuthService } from '../../core/auth.service';")
    lines.append("import { registerClear } from '../../core/state-registry';")
    lines.append('')

    def _interface(name: str, field_names: list) -> list:
        result = [f'export interface {name} {{']
        for f in field_names:
            if f in all_fields:
                ts = StoreGenerator.PY_TO_TS.get(_py_type_str(all_fields[f].py_type), 'unknown')
                result.append(f'  {f}: {ts};')
        result.append('}')
        return result

    lines += _interface(f'{iname}Out', out_names)
    lines.append('')
    if has_post:
        lines += _interface(f'{iname}PostIn', post_in_names)
        lines.append('')
    if has_put:
        lines += _interface(f'{iname}PutIn', put_in_names)
        lines.append('')

    lines.append(f"const _BASE = '{base_path}';")
    lines.append('')
    lines.append(f"@Injectable({{ providedIn: 'root' }})")
    lines.append(f'export class {iname}Store {{')
    lines.append('  private auth = inject(AuthService);')
    lines.append('  private http = inject(HttpClient);')
    lines.append('')

    if pk_field:
        lines.append(f'  readonly items = signal<{iname}Out[]>([]);')
        lines.append(f'  readonly byId  = signal(new Map<string, {iname}Out>());')
    else:
        lines.append(f'  readonly items = signal<{iname}Out[]>([]);')

    lines.append('')
    lines.append('  private loadedFilters = new Map<string, boolean>();  // Track fully loaded filter combinations')
    lines.append('  readonly hasMore = signal(true);  // Track if more data available')
    lines.append('  readonly currentOffset = signal(0);  // Current pagination offset')
    lines.append('  readonly isLoading = signal(false);  // Loading state')
    lines.append('')
    lines.append('  // Persisted UI state')
    lines.append('  readonly filters = signal<Record<string, string>>({});  // Active filters')
    lines.append('  readonly selectedId = signal<string | null>(null);  // Selected item ID')
    lines.append('  readonly sortField = signal<string | null>(null);  // Sort field')
    lines.append('  readonly sortAsc = signal(true);  // Sort direction')
    lines.append('')
    if pk_field:
        map_key_store = f'{schema_name}/{table_name}'
        lines.append(f'  constructor() {{')
        lines.append(f'    registerClear(() => this.clear());')
        lines.append(f"    this.auth.wsEvent$.pipe(filter(ev => ev.resource === '{map_key_store}')).subscribe(ev => {{")
        lines.append(f"      if (ev.event === 'delete') this.removeItem(String(ev.id));")
        lines.append(f"      else this.refresh(String(ev.id)).subscribe();")
        lines.append(f'    }});')
        lines.append(f'  }}')
    else:
        lines.append('  constructor() { registerClear(() => this.clear()); }')
    lines.append('')
    lines.append('  private get headers(): HttpHeaders {')
    lines.append('    const t = this.auth.token();')
    lines.append('    return t ? new HttpHeaders({ Authorization: `Bearer ${t}` }) : new HttpHeaders();')
    lines.append('  }')
    lines.append('')
    lines.append(f'  listUrl(params: Partial<{iname}Out> = {{}}): string {{')
    lines.append('    const filtered = Object.fromEntries(')
    lines.append('      Object.entries(params)')
    lines.append('        .filter(([_, v]) => v != null && (typeof v !== \'string\' || v !== \'\'))')
    lines.append('        .map(([k, v]) => [`ho_col_${k}`, v])')
    lines.append('    );')
    lines.append('    const qs = new URLSearchParams(filtered as any).toString();')
    lines.append('    return qs ? `${_BASE}?${qs}` : _BASE;')
    lines.append('  }')

    if pk_field:
        lines.append(f'  getUrl(id: string): string {{ return `${{_BASE}}/${{id}}`; }}')
        lines.append('')

    lines.append(f'  list(params: Partial<{iname}Out> = {{}}, offset: number = 0): void {{')
    lines.append('    const filterKey = JSON.stringify(params);')
    lines.append('    if (offset === 0 && this.loadedFilters.get(filterKey)) return;')
    lines.append('    if (this.isLoading()) return;')
    lines.append('')
    lines.append('    // Handle special \'q\' param for search (not prefixed with ho_col_)')
    lines.append('    const searchQ = (params as any)[\'q\'];')
    lines.append('    const otherParams = searchQ ? {} : params;')
    lines.append('    const baseUrl = this.listUrl(otherParams);')
    lines.append('    const separator = baseUrl.includes(\'?\') ? \'&\' : \'?\';')
    lines.append('    const urlParams = new URLSearchParams();')
    lines.append('    if (searchQ) urlParams.set(\'q\', searchQ);')
    lines.append('    if (offset > 0) urlParams.set(\'offset\', offset.toString());')
    lines.append('    urlParams.set(\'limit\', \'100\');')
    lines.append('    const queryString = urlParams.toString();')
    lines.append('    const url = queryString ? `${baseUrl}${separator}${queryString}` : baseUrl;')
    lines.append('    if (this.auth.fetchedRoutes.has(url)) return;')
    lines.append('    this.auth.fetchedRoutes.add(url);')
    lines.append('')
    lines.append('    this.isLoading.set(true);')
    lines.append(f'    this.http.get<{{data: {iname}Out[], meta: {{offset: number, limit: number, has_more: boolean}}}}>(url, {{ headers: this.headers }})')
    lines.append('      .pipe(catchError(() => of({ data: [], meta: { offset, limit: 100, has_more: false } })))')
    lines.append('      .subscribe(response => {')
    lines.append('        // Full unfiltered list replaces; filtered or paginated loads merge')
    lines.append('        if (offset === 0 && !searchQ && Object.keys(params).length === 0) this.setItems(response.data);')
    lines.append('        else this.mergeItems(response.data);')
    lines.append('        this.hasMore.set(response.meta.has_more);')
    lines.append('        this.currentOffset.set(offset + response.data.length);')
    lines.append('        this.isLoading.set(false);')
    lines.append('        if (!response.meta.has_more) this.loadedFilters.set(filterKey, true);')
    lines.append('      });')
    lines.append('  }')
    lines.append('')
    lines.append(f'  loadMore(params: Partial<{iname}Out> = {{}}): void {{')
    lines.append('    if (!this.hasMore() || this.isLoading()) return;')
    lines.append('    this.list(params, this.currentOffset());')
    lines.append('  }')
    lines.append('')
    lines.append('  resetFilterState(): void {')
    lines.append('    this.loadedFilters.clear();')
    lines.append('    this.hasMore.set(true);')
    lines.append('    this.currentOffset.set(0);')
    lines.append('  }')
    lines.append('')

    if pk_field:
        lines.append(f'  get(id: string) {{')
        lines.append('    const cached = this.byId().get(id);')
        lines.append('    if (cached) return of(cached);')
        lines.append('    return this.refresh(id);')
        lines.append('  }')
        lines.append('')
        lines.append(f'  refresh(id: string) {{')
        lines.append('    const url = this.getUrl(id);')
        lines.append('    this.auth.fetchedRoutes.add(url);')
        lines.append(f'    return this.http.get<{iname}Out>(url, {{ headers: this.headers }}).pipe(')
        lines.append('      tap(item => this.setItem(item)),')
        lines.append(f'      catchError(() => of(null as {iname}Out | null))')
        lines.append('    );')
        lines.append('  }')
        lines.append('')

    if has_post:
        lines.append(f'  create(data: {iname}PostIn) {{')
        lines.append(f'    return this.http.post<{iname}Out>(_BASE, data, {{')
        lines.append("      headers: this.headers.append('Content-Type', 'application/json')")
        lines.append('    });')
        lines.append('  }')
        lines.append('')

    if has_put and pk_field:
        lines.append(f'  update(id: string, data: {iname}PutIn) {{')
        lines.append(f'    return this.http.put<{iname}Out>(`${{_BASE}}/${{id}}`, data, {{')
        lines.append("      headers: this.headers.append('Content-Type', 'application/json')")
        lines.append('    });')
        lines.append('  }')
        lines.append('')

    if has_del and pk_field:
        lines.append(f'  remove(id: string) {{')
        lines.append(f'    return this.http.delete(`${{_BASE}}/${{id}}`, {{ headers: this.headers }});')
        lines.append('  }')
        lines.append('')

    if pk_field:
        lines.append(f'  setItems(data: {iname}Out[]): void {{')
        lines.append('    this.items.set(data);')
        lines.append(f'    this.byId.set(new Map(data.map(i => [({pk_extractor})(i), i])));')
        lines.append('  }')
        lines.append('')
        lines.append(f'  mergeItems(data: {iname}Out[]): void {{')
        lines.append('    const m = new Map(this.byId());')
        lines.append(f'    data.forEach(i => m.set(({pk_extractor})(i), i));')
        lines.append('    this.byId.set(m);')
        lines.append('    this.items.set([...m.values()]);')
        lines.append('  }')
        lines.append('')
        lines.append(f'  setItem(item: {iname}Out): void {{')
        lines.append('    const m = new Map(this.byId());')
        lines.append(f'    m.set(({pk_extractor})(item), item);')
        lines.append('    this.byId.set(m);')
        lines.append('    const arr = [...this.items()];')
        lines.append(f'    const idx = arr.findIndex(i => ({pk_extractor})(i) === ({pk_extractor})(item));')
        lines.append('    if (idx >= 0) arr[idx] = item; else arr.push(item);')
        lines.append('    this.items.set(arr);')
        lines.append('  }')
        lines.append('')
        lines.append('  removeItem(id: string): void {')
        lines.append('    const m = new Map(this.byId()); m.delete(id); this.byId.set(m);')
        lines.append(f'    this.items.set(this.items().filter(i => ({pk_extractor})(i) !== id));')
        lines.append('  }')
        lines.append('')
        lines.append('  clear(): void { this.items.set([]); this.byId.set(new Map()); }')
    else:
        lines.append(f'  setItems(data: {iname}Out[]): void {{ this.items.set(data); }}')
        lines.append(f'  mergeItems(data: {iname}Out[]): void {{ this.items.set([...this.items(), ...data]); }}')
        lines.append('  clear(): void { this.items.set([]); }')

    lines.append('}')
    lines.append('')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Per-resource components
# ---------------------------------------------------------------------------

def _list_component(
    schema_name: str, table_name: str,
    iname: str, map_key: str,
    out_names: list, pk_field: str | None, pk_ts_type: str, pk_extractor: str | None,
    has_post: bool, has_del: bool,
    fk_deps: list,
    all_fields: dict,
    pk_info: list | None = None,
) -> str:
    title  = _title(schema_name, table_name)
    fk_map = {lf: (rs, rt) for lf, rs, rt, _ in fk_deps}

    # Table headers (sortable)
    th_cols = '\n            '.join(
        f'<th (click)="sortBy(\'{f}\')"'
        f' class="px-4 py-2 text-left text-sm font-semibold text-gray-600'
        f' cursor-pointer select-none hover:bg-gray-200">'
        f'{f} {{{{ silo.sortField() === \'{f}\' ? (silo.sortAsc() ? \'↑\' : \'↓\') : \'\' }}}}</th>'
        for f in out_names
    )
    action_th = '<th class="px-2 py-2 w-16"></th>' if has_del and pk_field else ''

    # Filter row (one input per column, hidden when embedded)
    filter_inputs = '\n              '.join(
        f'<th class="px-2 py-1">'
        f'<input [value]="localFilters()[\'{f}\'] || \'\'"'
        f' (input)="setFilter(\'{f}\', $any($event).target.value)"'
        f' placeholder="…"'
        f' class="w-full text-xs border rounded px-2 py-1" /></th>'
        for f in out_names
    )
    action_filter_th = (
        '<th class="px-2 py-1">'
        '<button (click)="clearAllFilters()" '
        '[disabled]="Object.keys(localFilters()).length === 0" '
        'class="text-xs text-blue-600 hover:text-blue-800 disabled:text-gray-400 disabled:cursor-not-allowed" '
        'title="Clear all filters">✕</button>'
        '</th>'
    ) if has_del and pk_field else ''
    filter_row = (
        f'\n          @if (!embedded) {{\n'
        f'          <tr class="bg-white border-b">\n'
        f'              {action_filter_th}\n'
        f'              {filter_inputs}\n'
        f'          </tr>\n'
        f'          }}'
    )

    def _td(f: str) -> str:
        if f in fk_map:
            rs, rt = fk_map[f]
            return (
                f'<td class="px-4 py-2 text-sm">'
                f'<a [routerLink]="[\'/ho_bo/{rs}/{rt}\', String(item[\'{f}\'])]" (click)="$event.stopPropagation()"'
                f' class="text-blue-500 hover:underline font-mono text-xs truncate block max-w-xs"'
                f' [title]="cellTitle(item[\'{f}\'])">{{{{ fmtCell(item[\'{f}\']) }}}}</a>'
                f'</td>'
            )
        return (
            f'<td class="px-4 py-2 text-sm" (click)="cellClick($event, $any(item)[\'{f}\'])">'
            f'<div class="truncate max-w-xs" [title]="cellTitle(item[\'{f}\'])"'
            f' [class.text-blue-600]="$any(item)[\'{f}\'] != null && typeof $any(item)[\'{f}\'] === \'object\'"'
            f' [class.cursor-pointer]="$any(item)[\'{f}\'] != null && typeof $any(item)[\'{f}\'] === \'object\'">'
            f'{{{{ fmtCell(item[\'{f}\']) }}}}</div>'
            f'</td>'
        )

    td_cols = '\n              '.join(_td(f) for f in out_names)

    row_click = (
        f' (click)="selectAndNavigate(getPkId(item))"'
        if pk_field else ''
    )
    cursor = ' cursor-pointer' if pk_field else ''

    action_td = ''
    if has_del and pk_field:
        action_td = (
            '\n              <td class="px-2 py-2">\n'
            '                @if (canDelete()) {\n'
            f'                  <button (click)="handleDelete(getPkId(item), $event)"\n'
            '                          class="text-red-600 hover:underline text-sm">Delete</button>\n'
            '                }\n'
            '              </td>'
        )

    new_btn = ''
    if has_post:
        new_btn = (
            f'\n        @if (canCreate()) {{\n'
            f'          <a [routerLink]="[\'/ho_bo/{schema_name}/{table_name}/new\']"\n'
            f'             class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 text-sm">\n'
            f'            New\n          </a>\n        }}'
        )

    can_create = f"\n  readonly canCreate = computed(() => !!this.auth.access()['{map_key}']?.POST);" if has_post else ''
    can_delete = f"\n  readonly canDelete = computed(() => !!this.auth.access()['{map_key}']?.DELETE);" if has_del else ''

    delete_fn = ''
    if has_del and pk_field:
        delete_fn = (
            f'\n  handleDelete(id: string, e: Event): void {{\n'
            f'    e.stopPropagation();\n'
            f"    if (confirm('Delete this item?')) {{\n"
            f'      this.silo.remove(id).subscribe(() => this.silo.removeItem(String(id)));\n'
            f'    }}\n'
            f'  }}'
        )

    select_fn = ''
    if pk_field:
        select_fn = (
            f'\n  selectAndNavigate(id: string): void {{\n'
            f'    this.silo.selectedId.set(id);\n'
            f"    this.router.navigate(['/ho_bo/{schema_name}/{table_name}', id]);\n"
            f'  }}\n'
        )

    ws_effect = ''  # Store handles WS updates; list just reads reactively from store signals

    needs_router_link = has_post or bool(fk_deps)

    # single-PK: byId accumulates all fetched rows including setItem() calls
    # composite-PK or no PK: byId is never populated by the silo (pk=null), use items
    _is_single_pk = pk_field and (not pk_info or len(pk_info) == 1)
    if _is_single_pk:
        _fk_items_src = (
            'Array.from(this.silo.byId().values()).filter(item =>\n'
            '          Object.entries(this.filters).every(([k, v]) => String((item as any)[k]) === String(v)))'
        )
    else:
        _fk_items_src = (
            'this.silo.items().filter(item =>\n'
            '          Object.entries(this.filters).every(([k, v]) => String((item as any)[k]) === String(v)))'
        )

    # Generate field type map for validation
    field_types_entries = ', '.join(
        f"'{fname}': '{_field_type_category(all_fields[fname])}'"
        for fname in out_names if fname in all_fields
    )
    field_types_map = f"""
  private readonly fieldTypes: Record<string, FieldType> = {{
    {field_types_entries}
  }};"""

    displayItems_block = f"""\
  readonly displayItems = computed(() => {{
    const hasFilters = Object.keys(this.filters).length > 0;
    let items: Row[] = hasFilters
      ? {_fk_items_src}
      : this.silo.items();
    const lf = this.localFilters();
    if (Object.values(lf).some(v => v))
      items = items.filter(item =>
        Object.entries(lf).every(([k, v]) => matchFilter((item as any)[k], v)));
    const sf = this.silo.sortField();
    if (sf) {{
      const asc = this.silo.sortAsc();
      items = [...items].sort((a, b) => {{
        const av = String((a as any)[sf] ?? '');
        const bv = String((b as any)[sf] ?? '');
        return asc ? av.localeCompare(bv) : bv.localeCompare(av);
      }});
    }}
    return items;
  }});"""

    router_link_es  = "import { RouterLink } from '@angular/router';\n" if needs_router_link else ''
    router_link_imp = 'RouterLink' if needs_router_link else ''
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

    return f"""\
import {{ Component, computed, effect, inject, Input, signal, untracked, DestroyRef, afterNextRender, ViewChildren, QueryList, ElementRef }} from '@angular/core';
import {{ takeUntilDestroyed }} from '@angular/core/rxjs-interop';
import {{ filter }} from 'rxjs';
{router_link_es}import {{ Router, ActivatedRoute }} from '@angular/router';
import {{ Location }} from '@angular/common';
import {{ SiloRegistry }} from '../../../generated/silo-registry.service';
import type {{ Row }} from '../../../generated/resource.silo';
import {{ AuthService }} from '../../../core/auth.service';
import {{ isValidFilterValue, normalizeFilterValue, matchFilter, fmtCell, cellTitle, parseFiltersFromUrl, encodeFiltersToUrlParams }} from '../../../generated/stores/filters';
import type {{ FieldType }} from '../../../generated/stores/filters';

@Component({{
  selector: '{_selector(schema_name, table_name, 'list')}',
  standalone: true,
  imports: [{router_link_imp}],
  template: `
    @if (!embedded) {{
      <div class="flex justify-between items-center mb-4">
        <h1 class="text-2xl font-bold">{title}</h1>{new_btn}
      </div>
    }}
    <div [class]="embedded ? '' : 'bg-white shadow-sm rounded-lg overflow-auto max-h-[calc(100vh-10rem)]'">
      <table class="w-full border-collapse">
        <thead [class]="embedded ? 'bg-gray-100' : 'bg-gray-100 sticky top-0 z-10 shadow-sm'">
          <tr>
            {action_th}
            {th_cols}
          </tr>{filter_row}
        </thead>
        <tbody>
          @for (item of displayItems(); track $index) {{
            <tr #dataRow class="border-t hover:bg-gray-50{cursor}"{row_click}{highlight_attrs}>
              {action_td}
              {td_cols}
            </tr>
          }}
          @if (silo.isLoading()) {{
            <tr><td colspan="100" class="text-center py-4 text-gray-500">Loading...</td></tr>
          }}
        </tbody>
      </table>
    </div>
    @if (jsonDialogContent() !== null) {{
      <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
           (click)="jsonDialogContent.set(null)">
        <div class="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 p-6"
             (click)="$event.stopPropagation()">
          <div class="flex justify-between items-center mb-3">
            <h3 class="font-semibold text-gray-800">JSON</h3>
            <button (click)="jsonDialogContent.set(null)"
                    class="text-gray-400 hover:text-gray-600 text-xl leading-none">✕</button>
          </div>
          <pre class="text-xs bg-gray-50 rounded p-4 overflow-auto max-h-[60vh] whitespace-pre-wrap">{{{{ jsonDialogContent() }}}}</pre>
        </div>
      </div>
    }}
  `
}})
export class {iname}ListComponent {{
  protected silo   = inject(SiloRegistry).get('{map_key}');
  protected auth   = inject(AuthService);
  protected router = inject(Router);
  private route = inject(ActivatedRoute);
  private location = inject(Location);
  protected String = String;  // For template use
  protected Object = Object;  // For template use
  protected matchFilter = matchFilter;  // For template use
  protected fmtCell = fmtCell;  // For template use
  protected cellTitle = cellTitle;  // For template use{pk_id_line}
  private destroyRef = inject(DestroyRef);

  @ViewChildren('dataRow') dataRows!: QueryList<ElementRef<HTMLTableRowElement>>;
  private observer?: IntersectionObserver;
  private currentLastElement?: Element;
  private filterDebounceTimer?: number;
  private hadFilters = false;

  @Input() filters: Partial<Row> = {{}};
  @Input() embedded = false;

  localFilters = signal<Record<string, string>>({{}});
{can_create}{can_delete}
{field_types_map}
{displayItems_block}

  constructor() {{
    // Initialize filters from URL or store before loading data
    this.initFiltersFromUrl();

    effect(() => {{
      const _token = this.auth.token();
      this.silo.list(this.filters);
    }});{ws_effect}

    // Set up observer
    this.observer = new IntersectionObserver(
      (entries) => {{
        if (entries[0].isIntersecting && this.silo.hasMore() && !this.silo.isLoading()) {{
          this.silo.loadMore(this.filters);
        }}
      }},
      {{ rootMargin: '0px 0px 400px 0px' }}
    );

    // Re-observe when items change (must be in constructor for injection context)
    effect(() => {{
      this.silo.items().length;  // Track changes
      untracked(() => {{
        setTimeout(() => this.updateObservedElement(), 0);
      }});
    }});

    // Initial observation after render
    afterNextRender(() => {{
      this.updateObservedElement();
    }});

    this.destroyRef.onDestroy(() => {{
      this.observer?.disconnect();
    }});
  }}

  private updateObservedElement() {{
    if (this.currentLastElement) this.observer?.unobserve(this.currentLastElement);
    const rows = this.dataRows.toArray();
    if (rows.length > 0) {{
      const lastElement = rows[rows.length - 1].nativeElement;
      this.currentLastElement = lastElement;
      this.observer?.observe(lastElement);
    }}
  }}

  sortBy(f: string): void {{
    if (this.silo.sortField() === f) this.silo.sortAsc.set(!this.silo.sortAsc());
    else {{ this.silo.sortField.set(f); this.silo.sortAsc.set(true); }}
  }}
  setFilter(f: string, v: string): void {{
    const updated = {{ ...this.localFilters(), [f]: v }};
    this.localFilters.set(updated);

    // Apply filters on backend with debounce
    if (this.filterDebounceTimer) clearTimeout(this.filterDebounceTimer);
    this.filterDebounceTimer = window.setTimeout(() => {{
      // Convert local filters to backend search query (q=col1:val1,col2:val2)
      // Only include valid filters based on field type
      const filterPairs: string[] = [];
      Object.entries(updated).forEach(([key, val]) => {{
        if (val && isValidFilterValue(key, val, this.fieldTypes)) {{
          const normalizedVal = normalizeFilterValue(key, val, this.fieldTypes);
          filterPairs.push(`${{key}}:${{normalizedVal}}`);
        }}
      }});
      const hasFiltersNow = filterPairs.length > 0;

      // Update URL with current filters
      this.syncFiltersToUrl(updated);

      // Only trigger if we have filters now, or we had filters before (to clear them)
      if (hasFiltersNow || this.hadFilters) {{
        this.hadFilters = hasFiltersNow;
        // Reset pagination state and clear loaded filters cache
        this.silo.resetFilterState();
        const searchParams = hasFiltersNow ? {{ q: filterPairs.join(',') }} as any : {{}};
        this.silo.list(searchParams, 0);
      }}
    }}, 600);
  }}
  jsonDialogContent = signal<string | null>(null);
  showJson(v: unknown): void {{ this.jsonDialogContent.set(JSON.stringify(v, null, 2)); }}
  cellClick(e: Event, v: unknown): void {{
    if (v != null && typeof v === 'object') {{ e.stopPropagation(); this.showJson(v); }}
  }}

  private initFiltersFromUrl(): void {{
    if (this.embedded) return; // Don't sync URL for embedded components

    const params = this.route.snapshot.queryParams;
    const urlFilters = parseFiltersFromUrl(params, this.fieldTypes);

    // If URL has filters, use them (priority)
    if (Object.keys(urlFilters).length > 0) {{
      this.localFilters.set(urlFilters);
      this.silo.filters.set(urlFilters);
    }} else {{
      // Otherwise, try to restore from store
      const storeFilters = this.silo.filters();
      if (Object.keys(storeFilters).length > 0) {{
        this.localFilters.set(storeFilters);
        // Update URL to reflect store filters
        this.syncFiltersToUrl(storeFilters);
      }}
    }}
  }}

  private syncFiltersToUrl(filters: Record<string, string>): void {{
    if (this.embedded) return; // Don't sync URL for embedded components

    // Update store with current filters
    this.silo.filters.set(filters);

    const queryParams: Record<string, string> = {{}};

    // Preserve non-filter params
    Object.entries(this.route.snapshot.queryParams).forEach(([key, value]) => {{
      if (!key.startsWith('f_') && typeof value === 'string') {{
        queryParams[key] = value;
      }}
    }});

    // Add filter params (using shared function)
    const filterParams = encodeFiltersToUrlParams(filters, this.fieldTypes);
    Object.assign(queryParams, filterParams);

    // Use replaceState to avoid polluting browser history
    const urlTree = this.router.createUrlTree([], {{
      relativeTo: this.route,
      queryParams,
      queryParamsHandling: '' // Replace all params
    }});

    this.location.replaceState(urlTree.toString());
  }}

  clearAllFilters(): void {{
    this.localFilters.set({{}});
    this.syncFiltersToUrl({{}});
  }}{select_fn}{delete_fn}
}}
"""


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
) -> str:
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

    return f"""\
import {{ Component, inject, signal }} from '@angular/core';
import {{ FormsModule }} from '@angular/forms';
import {{ RouterLink, Router }} from '@angular/router';
import {{ SiloRegistry }} from '../../../generated/silo-registry.service';
import type {{ Row }} from '../../../generated/resource.silo';

@Component({{
  selector: '{_selector(schema_name, table_name, 'create')}',
  standalone: true,
  imports: [FormsModule, RouterLink],
  template: `
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
  `
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


def _fields_component(
    schema_name: str, table_name: str,
    iname: str, pk_field: str, pk_info: list,
    out_names: list, fk_deps: list, all_fields: dict,
) -> str:
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

    return f"""\
import {{ Component, input }} from '@angular/core';
import {{ RouterLink }} from '@angular/router';{latex_import}
import type {{ Row }} from '../../resource.silo';

@Component({{
  selector: '{_selector(schema_name, table_name, 'fields')}',
  standalone: true,
  imports: [{all_imports}],
  template: `
    <div class="space-y-2">
      {rows}
    </div>
  `
}})
export class {iname}FieldsComponent {{
  readonly item    = input.required<Row>();
  readonly hidePk  = input<boolean>(false);
  protected String = String;
}}
"""


def _detail_component(
    schema_name: str, table_name: str,
    iname: str, pk_field: str, pk_ts_type: str, pk_extractor: str,
    out_names: list, put_in_names: list,
    has_put: bool, map_key: str,
    fk_deps: list, rev_fk_deps: list,
    all_fields: dict,
) -> str:
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
        @if (registry.tryGet('{fk_key}')?.byId()?.get(String(item()!['{lf}'])); as ref) {{
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

    return f"""\
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
  template: `
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
  `
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
  readonly item = computed<Row | null>(() => this.silo.byId().get(this.id) ?? null);
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
        package_dir = Path(__file__).parent.parent
        filters_src = package_dir / 'templates_filters.ts'
        if filters_src.exists():
            shutil.copy2(filters_src, stores_dir / 'filters.ts')
            print(f'  {stores_dir / "filters.ts"}')

        # --- shared silo files (SiloRegistry / ResourceSilo / schema types) ---
        angular_assets = Path(__file__).parent / 'assets' / 'angular'
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

            self._write(comp_dir / 'list.component.ts',
                        _list_component(schema_name, table_name, iname, map_key,
                                        out_names, pk_field, pk_ts_type, pk_extractor, has_post, has_del, fk_deps, all_fields, pk_info))

            if has_post:
                self._write(comp_dir / 'create.component.ts',
                            _create_component(schema_name, table_name, iname,
                                              post_in_names, all_fields, optional_post_fields))

            if has_detail:
                self._write(comp_dir / 'fields.component.ts',
                            _fields_component(schema_name, table_name, iname,
                                              pk_field, pk_cols, out_names, fk_deps, all_fields))
                self._write(comp_dir / 'detail.component.ts',
                            _detail_component(schema_name, table_name, iname,
                                              pk_field, pk_ts_type, pk_extractor,
                                              out_names, put_in_names, has_put,
                                              map_key, fk_deps, rev_fk_deps, all_fields))

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
