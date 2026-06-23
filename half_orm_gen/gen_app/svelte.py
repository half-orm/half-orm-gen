"""
SvelteKit 5 backoffice generator.

Produces a SvelteKit app (Tailwind + TypeScript + Svelte 5 runes) with:
  - src/lib/generated/stores/      — regenerable stores + API clients
  - src/lib/generated/components/  — regenerable List/CreateForm/DetailView components
  - src/routes/(admin)/            — thin page wrappers (auth-guarded)
"""

import importlib
import shutil
from pathlib import Path

from half_orm_gen.crud_routes import (
    _gen_out_fields,
    _gen_in_fields,
    _pk_info,
    _simple_pk,
    _instance,
    _py_type_str,
)
from half_orm_gen.gen_store.svelte import SvelteGenerator
from half_orm_gen.gen_store.base import StoreGenerator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Static file templates
# ---------------------------------------------------------------------------

_PACKAGE_JSON = """\
{{
  "name": "{project_name}",
  "version": "0.0.1",
  "private": true,
  "type": "module",
  "scripts": {{
    "prepare": "svelte-kit sync || true",
    "dev": "vite dev",
    "build": "vite build",
    "preview": "vite preview",
    "check": "svelte-kit sync && svelte-check --tsconfig ./tsconfig.json",
    "check:watch": "svelte-kit sync && svelte-check --tsconfig ./tsconfig.json --watch"
  }},
  "dependencies": {{
    "katex": "^0.16.0"
  }},
  "devDependencies": {{
    "@sveltejs/adapter-auto": "^7.0.0",
    "@sveltejs/kit": "^2.65.2",
    "@sveltejs/vite-plugin-svelte": "^7.0.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0",
    "svelte": "^5.46.4",
    "svelte-check": "^4.0.0",
    "tailwindcss": "^3.4.0",
    "typescript": "^5.0.0",
    "vite": "^8.0.0"
  }}
}}
"""

_SVELTE_CONFIG = """\
import adapter from '@sveltejs/adapter-auto';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

const config = {
  preprocess: vitePreprocess(),
  kit: { adapter: adapter() }
};

export default config;
"""

_VITE_CONFIG = """\
import {{ sveltekit }} from '@sveltejs/kit/vite';
import {{ defineConfig }} from 'vite';

export default defineConfig({{
  plugins: [sveltekit()],
  server: {{
    proxy: {{
      '{version_prefix}': {{ target: 'http://localhost:8000', ws: true }},
    }}
  }}
}});
"""

_TSCONFIG = """\
{
  "extends": "./.svelte-kit/tsconfig.json",
  "compilerOptions": {
    "allowJs": true,
    "checkJs": true,
    "esModuleInterop": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "skipLibCheck": true,
    "sourceMap": true,
    "strict": true
  }
}
"""

_TAILWIND_CONFIG = """\
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{html,js,svelte,ts}'],
  theme: { extend: {} },
  plugins: []
};
"""

_POSTCSS_CONFIG = """\
export default {
  plugins: { tailwindcss: {}, autoprefixer: {} }
};
"""

_APP_HTML = """\
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <link rel="icon" href="%sveltekit.assets%/favicon.png" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    %sveltekit.head%
  </head>
  <body data-sveltekit-preload-data="hover">
    <div style="display: contents">%sveltekit.body%</div>
  </body>
</html>
"""

_APP_CSS = """\
@import 'katex/dist/katex.min.css';
@tailwind base;
@tailwind components;
@tailwind utilities;
"""

_LATEX_TS = """\
import katex from 'katex';

export function renderLatex(raw: unknown): string {
    const text = String(raw ?? '');
    if (!text || (!text.includes('$') && !text.includes('\\\\('))) return escHtml(text);
    const parts = text.split(/(\\$\\$[\\s\\S]+?\\$\\$|\\$[^$\\n]+?\\$)/g);
    return parts.map((part, i) => {
        if (i % 2 === 0) return escHtml(part);
        const display = part.startsWith('$$');
        const math = display ? part.slice(2, -2) : part.slice(1, -1);
        return katex.renderToString(math, { displayMode: display, throwOnError: false });
    }).join('');
}

function escHtml(s: string): string {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/\\n/g, '<br>');
}
"""

def _auth_store(version_prefix: str) -> str:
    return f"""\
import {{ goto }} from '$app/navigation';
import {{ clearAllStates }} from '$lib/stateRegistry';

export type WsEvent = {{ event: 'create' | 'update' | 'delete'; resource: string; id: unknown }};

class AuthState {{
    token         = $state<string | null>(
        typeof sessionStorage !== 'undefined' ? sessionStorage.getItem('ho_token') : null
    );
    access        = $state<Record<string, any>>({{}});
    lastEvent     = $state<WsEvent | null>(null);
    fetchedRoutes = new Set<string>();

    login(t: string) {{
        sessionStorage.setItem('ho_token', t);
        this.token = t;
        this.fetchedRoutes = new Set();
        clearAllStates();
        this._fetchAccess();
    }}

    logout() {{
        sessionStorage.removeItem('ho_token');
        this.token = null;
        this.fetchedRoutes = new Set();
        clearAllStates();

        // Clear filter query params on logout
        if (typeof window !== 'undefined' && window.location.search.includes('f_')) {{
            const currentPath = window.location.pathname;
            goto(currentPath, {{ replaceState: true }});
        }}

        this._fetchAccess();
    }}

    async _fetchAccess() {{
        const hdrs: Record<string, string> = this.token
            ? {{ Authorization: `Bearer ${{this.token}}` }}
            : {{}};
        try {{
            const res = await fetch('{version_prefix}/ho_access', {{ headers: hdrs }});
            this.access = res.ok ? await res.json() : {{}};
        }} catch {{
            this.access = {{}};
        }}
    }}

    _connectWs() {{
        const base = (import.meta.env.VITE_WS_BASE ?? '').replace(/^http/, 'ws')
                     || `${{window.location.protocol === 'https:' ? 'wss' : 'ws'}}://${{window.location.host}}`;
        const ws = new WebSocket(`${{base}}{version_prefix}/ws`);
        ws.onmessage = (e) => {{
            try {{ this.lastEvent = JSON.parse(e.data) as WsEvent; }} catch {{}}
        }};
        ws.onclose = () => {{ setTimeout(() => this._connectWs(), 2000); }};
        ws.onerror = () => ws.close();
    }}
}}

export const auth = new AuthState();

if (typeof window !== 'undefined') {{
    auth._fetchAccess();
    auth._connectWs();
}}
"""

def _login_page(version_prefix: str) -> str:
    return f"""\
<script lang="ts">
  import {{ auth }} from '$lib/auth.svelte.ts';
  import {{ goto }} from '$app/navigation';
  import {{ onMount }} from 'svelte';

  let roles   = $state<string[]>([]);
  let loading = $state(true);
  let error   = $state('');

  onMount(() => {{
    fetch('{version_prefix}/ho_roles')
      .then(r => {{ if (!r.ok) throw new Error(r.statusText); return r.json(); }})
      .then(d  => {{ roles = d; loading = false; }})
      .catch(e => {{ error = e.message; loading = false; }});
  }});

  function selectRole(role: string) {{
    auth.login(role);
    goto('/ho_bo');
  }}
</script>

<div class="max-w-sm mx-auto mt-16 p-6 bg-white rounded-lg shadow">
  <h1 class="text-xl font-bold mb-2">Select a role</h1>
  <p class="text-xs text-gray-400 mb-6">Dev mode — the role name is used as bearer token.</p>

  {{#if loading}}
    <p class="text-gray-400 text-sm">Loading roles…</p>
  {{:else if error}}
    <p class="text-red-500 text-sm">{{error}}</p>
  {{:else if roles.length === 0}}
    <p class="text-gray-500 text-sm">No roles found.</p>
  {{:else}}
    <div class="space-y-2">
      {{#each roles as role}}
        <button onclick={{() => selectRole(role)}}
                class="w-full text-left px-4 py-3 border rounded hover:bg-blue-50
                       hover:border-blue-300 transition-colors text-sm font-medium">
          {{role}}
        </button>
      {{/each}}
    </div>
  {{/if}}
</div>
"""

def _home_page() -> str:
    return """\
<div class="flex flex-col items-center justify-center h-screen bg-gray-50">
  <div class="flex items-center gap-6 mb-6">
    <img src="/logo.png" alt="halfORM" class="h-30 w-auto" />
  </div>
  <h1 class="text-3xl font-bold text-gray-800 mb-2">halfORM Backoffice</h1>
  <div class="text-gray-500">Powered by SvelteKit</div>
  <div class="mb-8">
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 107 128" width="33" height="40">
      <path d="M94.1566,22.8189c-10.4-14.8851-30.94-19.2971-45.7914-9.8348L22.2825,29.6078A29.9234,29.9234,0,0,0,8.7639,49.6506a31.5136,31.5136,0,0,0,3.1076,20.2318A30.0061,30.0061,0,0,0,7.3953,81.0653a31.8886,31.8886,0,0,0,5.4473,24.1157c10.4022,14.8865,30.9423,19.2966,45.7914,9.8348L84.7167,98.3921A29.9177,29.9177,0,0,0,98.2353,78.3493,31.5263,31.5263,0,0,0,95.13,58.117a30,30,0,0,0,4.4743-11.1824,31.88,31.88,0,0,0-5.4473-24.1157" fill="#FF3E00"/>
      <path d="M45.8171,106.5815A20.7182,20.7182,0,0,1,23.58,98.3389a19.1739,19.1739,0,0,1-3.2766-14.5025,18.1886,18.1886,0,0,1,.6233-2.4357l.4912-1.4978,1.3363.9815a33.6443,33.6443,0,0,0,10.203,5.0978l.9694.2941-.0893.9675a5.8474,5.8474,0,0,0,1.052,3.8781,6.2389,6.2389,0,0,0,6.6952,2.485,5.7449,5.7449,0,0,0,1.6021-.7041L69.27,76.281a5.4306,5.4306,0,0,0,2.4506-3.631,5.7948,5.7948,0,0,0-.9875-4.3712,6.2436,6.2436,0,0,0-6.6978-2.4864,5.7427,5.7427,0,0,0-1.6.7036l-9.9532,6.3449a19.0329,19.0329,0,0,1-5.2965,2.3259,20.7181,20.7181,0,0,1-22.2368-8.2427,19.1725,19.1725,0,0,1-3.2766-14.5024,17.9885,17.9885,0,0,1,8.13-12.0513L55.8833,23.7472a19.0038,19.0038,0,0,1,5.3-2.3287A20.7182,20.7182,0,0,1,83.42,29.6611a19.1739,19.1739,0,0,1,3.2766,14.5025,18.4,18.4,0,0,1-.6233,2.4357l-.4912,1.4978-1.3356-.98a33.6175,33.6175,0,0,0-10.2037-5.1l-.9694-.2942.0893-.9675a5.8588,5.8588,0,0,0-1.052-3.878,6.2389,6.2389,0,0,0-6.6952-2.485,5.7449,5.7449,0,0,0-1.6021.7041L37.73,51.719a5.4218,5.4218,0,0,0-2.4487,3.63,5.7862,5.7862,0,0,0,.9856,4.3717,6.2437,6.2437,0,0,0,6.6978,2.4864,5.7652,5.7652,0,0,0,1.602-.7041l9.9519-6.3425a18.978,18.978,0,0,1,5.2959-2.3278,20.7181,20.7181,0,0,1,22.2368,8.2427,19.1725,19.1725,0,0,1,3.2766,14.5024,17.9977,17.9977,0,0,1-8.13,12.0532L51.1167,104.2528a19.0038,19.0038,0,0,1-5.3,2.3287" fill="#fff"/>
    </svg>
  </div>
  <a href="/ho_bo"
     class="bg-orange-500 text-white px-6 py-3 rounded-lg hover:bg-orange-600 font-medium transition-colors">
    Open Backoffice →
  </a>
</div>
"""

def _access_page(version_prefix: str) -> str:
    return f"""\
<script lang="ts">
  import {{ auth }} from '$lib/auth.svelte.ts';
  import {{ onMount }} from 'svelte';

  let roles        = $state<string[]>([]);
  let rolesLoading = $state(true);

  const activeRole = $derived(auth.token ?? 'public');

  onMount(() => {{
    fetch('{version_prefix}/ho_roles')
      .then(r => r.json())
      .then(d => {{ roles = d; rolesLoading = false; }});
  }});

  function selectRole(role: string) {{
    if (role === 'public') auth.logout();
    else auth.login(role);
  }}

  const VERB_COLOR: Record<string, string> = {{
    GET:    'bg-blue-100 text-blue-700',
    POST:   'bg-green-100 text-green-700',
    PUT:    'bg-yellow-100 text-yellow-700',
    DELETE: 'bg-red-100 text-red-700',
  }};
</script>

<div class="flex h-full gap-6">
  <div class="w-44 shrink-0">
    <h2 class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Roles</h2>
    {{#if rolesLoading}}
      <p class="text-gray-400 text-sm">Loading…</p>
    {{:else}}
      <div class="space-y-1">
        {{#each roles as role}}
          <button
            onclick={{() => selectRole(role)}}
            class="w-full text-left px-3 py-2 rounded text-sm transition-colors
                   {{activeRole === role ? 'bg-blue-600 text-white font-semibold' : 'text-gray-700 hover:bg-gray-100'}}">
            {{role}}
          </button>
        {{/each}}
      </div>
    {{/if}}
  </div>

  <div class="flex-1 min-w-0">
    <h1 class="text-2xl font-bold mb-6">
      Authorizations
      <span class="text-base font-normal text-gray-500">— {{activeRole}}</span>
    </h1>

    {{#if Object.keys(auth.access).length === 0}}
      <p class="text-gray-500 text-sm">No access granted for this role.</p>
    {{:else}}
      <div class="space-y-4">
        {{#each Object.entries(auth.access) as [resource, verbs]}}
          <div class="bg-white rounded-lg shadow-sm overflow-hidden">
            <div class="px-4 py-2 bg-gray-100 font-semibold text-gray-700 text-sm">{{resource}}</div>
            <div class="divide-y">
              {{#each Object.entries(verbs) as [verb, info]}}
                <div class="px-4 py-3 flex gap-4 items-start text-sm">
                  <span class="inline-block px-2 py-0.5 rounded font-mono text-xs font-bold w-16 text-center {{VERB_COLOR[verb] ?? 'bg-gray-100 text-gray-600'}}">
                    {{verb}}
                  </span>
                  <div class="text-gray-700">
                    {{#if verb === 'DELETE'}}
                      <span class="text-green-600">allowed</span>
                    {{:else if verb === 'GET'}}
                      <span class="text-gray-400">out: </span>{{(info?.out ?? []).join(', ')}}
                    {{:else}}
                      <div><span class="text-gray-400">in:  </span>{{(info?.in  ?? []).join(', ')}}</div>
                      <div><span class="text-gray-400">out: </span>{{(info?.out ?? []).join(', ')}}</div>
                    {{/if}}
                  </div>
                </div>
              {{/each}}
            </div>
          </div>
        {{/each}}
      </div>
    {{/if}}
  </div>
</div>
"""


# ---------------------------------------------------------------------------
# Dynamic template helpers
# ---------------------------------------------------------------------------

def _title(schema_name: str, table_name: str) -> str:
    return f'{schema_name}.{table_name}'


def _layout(resources: list) -> str:
    nav_items_js = ',\n    '.join(
        f'{{ href: "/ho_bo/{sn}/{tn}", label: "{_title(sn, tn)}" }}'
        for sn, tn, *_ in resources
    )
    return f"""\
<script lang="ts">
  import '../../app.css';
  import {{ auth }} from '$lib/auth.svelte.ts';

  let {{ children }} = $props();
  let navFilter = $state('');
  const navItems = [
    {nav_items_js}
  ].sort((a, b) => a.label.localeCompare(b.label));
  const filteredNav = $derived(
    navFilter
      ? navItems.filter(i => i.label.toLowerCase().includes(navFilter.toLowerCase()))
      : navItems
  );
</script>

<div class="h-screen flex flex-col bg-gray-50 overflow-hidden">
  <header class="shrink-0 bg-white border-b h-11 flex items-center justify-between px-4">
    <span class="font-bold text-gray-800">halfORM Backoffice</span>
    <a href="/ho_bo"
       class="text-xs px-3 py-1 rounded-full border border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100 transition-colors">
      {{auth.token ?? 'public'}}
    </a>
  </header>
  <div class="flex flex-1 overflow-hidden">
    <aside class="w-56 shrink-0 bg-white border-r flex flex-col">
      <div class="px-2 pt-2 pb-1">
        <input bind:value={{navFilter}} placeholder="Filter…"
               class="w-full text-xs border rounded px-2 py-1 text-gray-700"/>
      </div>
      <nav class="flex-1 overflow-y-auto px-2 py-2 space-y-0.5">
        {{#each filteredNav as item}}
          <a href={{item.href}}
             class="block px-3 py-2 rounded hover:bg-gray-100 text-sm text-gray-700">
            {{item.label}}
          </a>
        {{/each}}
      </nav>
      <div class="px-4 py-3 border-t">
        <a href="/">
          <img src="/logo.png" alt="halfORM" class="h-10 w-auto opacity-80 hover:opacity-100 transition-opacity" />
        </a>
      </div>
    </aside>
    <main class="flex-1 overflow-y-auto p-6">
      {{@render children()}}
    </main>
  </div>
</div>
"""


def _cname(schema_name: str, table_name: str) -> str:
    """PascalCase component/interface name — e.g. BlogComment"""
    schema_name = schema_name.replace('.', '_')
    return ''.join(p.capitalize() for p in f'{schema_name}_{table_name}'.split('_'))


def _rname(schema_name: str, table_name: str) -> str:
    """camelCase resource name — e.g. blogComment"""
    schema_name = schema_name.replace('.', '_')
    parts = schema_name.split('_') + table_name.split('_')
    return parts[0].lower() + ''.join(p.capitalize() for p in parts[1:])


def _list_component(
    schema_name: str, table_name: str,
    stem: str, rname: str, iname: str,
    out_names: list, pk_info: list,
    has_post: bool, has_del: bool,
    map_key: str,
    fk_deps: list,
    all_fields: dict,
) -> str:
    pk_field = pk_info[0][0] if pk_info else None
    if len(pk_info) == 1:
        pk_item_expr = f'item.{pk_field}'
        pk_item_url = f'${{item.{pk_field}}}'
    elif len(pk_info) > 1:
        # New format: col1:val1::col2:val2
        parts = '::'.join(f'{f}:${{item.{f}}}' for f, _, _ in pk_info)
        pk_item_expr = f'`{parts}`'  # For use in onclick handlers (standalone expression)
        pk_item_url = parts  # For use in template strings (no outer backticks)
    else:
        pk_item_expr = None
        pk_item_url = None
    title    = _title(schema_name, table_name)
    fk_map   = {local: (rs, rt) for local, rs, rt, _ in fk_deps}

    def _sort_th(f: str) -> str:
        toggle = (
            f"() => {{ if ({rname}State.sortField === '{f}') {rname}State.sortAsc = !{rname}State.sortAsc;"
            f" else {{ {rname}State.sortField = '{f}'; {rname}State.sortAsc = true; }} }}"
        )
        indicator = f"{{#if {rname}State.sortField === '{f}'}}{{{rname}State.sortAsc ? '↑' : '↓'}}{{/if}}"
        return (
            f'<th onclick={{{toggle}}}'
            f' class="px-4 py-2 text-left text-sm font-semibold text-gray-600'
            f' cursor-pointer select-none hover:bg-gray-200">'
            f'{f} {indicator}</th>'
        )

    action_th = '<th class="px-2 py-2 w-16"></th>' if has_del and pk_field else ''
    th_cols   = (action_th + '\n        ' if action_th else '') + '\n        '.join(_sort_th(f) for f in out_names)

    filter_inputs = '\n        '.join(
        f'<th class="px-2 py-1">'
        f'<input value={{localFilters[\'{f}\'] ?? \'\'}} '
        f'oninput={{(e) => localFilters = {{...localFilters, \'{f}\': e.currentTarget.value}}}} '
        f'placeholder="…" class="w-full text-xs border rounded px-2 py-1 font-normal" /></th>'
        for f in out_names
    )
    action_filter_th = (
        '<th class="px-2 py-1">'
        '<button onclick={() => clearAllFilters()} '
        'disabled={Object.keys(localFilters).length === 0} '
        'class="text-xs text-blue-600 hover:text-blue-800 disabled:text-gray-400 disabled:cursor-not-allowed" '
        'title="Clear all filters">✕</button>'
        '</th>'
    ) if has_del and pk_field else ''
    filter_row = (
        f'\n      {{#if !embedded}}\n'
        f'      <tr class="bg-white border-b">\n'
        f'        {action_filter_th}\n'
        f'        {filter_inputs}\n'
        f'      </tr>\n'
        f'      {{/if}}'
    )

    def _td(f: str) -> str:
        if f in fk_map:
            rs, rt = fk_map[f]
            return (
                f'<td class="px-4 py-2 text-sm">'
                f'<a href="/ho_bo/{rs}/{rt}/{{item.{f}}}"'
                f' onclick={{(e) => {{ e.preventDefault(); e.stopPropagation(); goto(`/ho_bo/{rs}/{rt}/${{item.{f}}}`); }}}}'
                f' class="text-blue-500 hover:underline font-mono text-xs truncate block max-w-xs"'
                f' title="{{cellTitle(item.{f})}}">{{fmtCell(item.{f})}}</a>'
                f'</td>'
            )
        cell_click = (
            f"(e) => {{ const _j = (item as any).{f}; "
            f"if (_j != null && typeof _j === 'object') {{ e.stopPropagation(); showJson(_j); }} }}"
        )
        return (
            f'<td class="px-4 py-2 text-sm" onclick={{{cell_click}}}>'
            f'<div class="truncate max-w-xs" title="{{cellTitle(item.{f})}}"'
            f' class:text-blue-600={{typeof (item as any).{f} === \'object\' && (item as any).{f} != null}}'
            f' class:cursor-pointer={{typeof (item as any).{f} === \'object\' && (item as any).{f} != null}}>'
            f'{{fmtCell(item.{f})}}</div></td>'
        )

    td_cols = '\n          '.join(_td(f) for f in out_names)

    if pk_field:
        tr_attrs = (
            f'class="border-t hover:bg-gray-50 cursor-pointer" '
            f'class:bg-blue-50={{{rname}State.selectedId === String({pk_item_expr})}} '
            f'class:border-l-4={{{rname}State.selectedId === String({pk_item_expr})}} '
            f'class:border-l-blue-500={{{rname}State.selectedId === String({pk_item_expr})}} '
            f'data-item-id={{String({pk_item_expr})}} '
            f'onclick={{() => selectAndNavigate(String({pk_item_expr}))}}'
        )
    else:
        tr_attrs = 'class="border-t hover:bg-gray-50"'

    action_td = ''
    if has_del and pk_field:
        action_td = (
            f'<td class="px-2 py-2">\n'
            f'          {{#if canDelete}}\n'
            f'            <button'
            f' onclick={{(e) => {{ e.stopPropagation(); handleDelete({pk_item_expr}); }}}}'
            f'\n                    class="text-red-600 hover:underline text-sm">Delete</button>\n'
            f'          {{/if}}\n'
            f'        </td>'
        )

    new_btn = (
        f'\n  {{#if canCreate}}\n'
        f'    <a href="/ho_bo/{schema_name}/{table_name}/new"\n'
        f'       class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 text-sm">\n'
        f'      New\n    </a>\n  {{/if}}'
        if has_post else ''
    )

    can_create = f"\n  const canCreate = $derived(!embedded && !!auth.access['{map_key}']?.POST);" if has_post else ''
    can_delete = f"\n  const canDelete  = $derived(!!auth.access['{map_key}']?.DELETE);" if has_del else ''
    delete_fn  = (
        f'\n  async function handleDelete(id: string) {{\n'
        f'    if (confirm(\'Delete this item?\')) {{\n'
        f'      const res = await {rname}Api.remove(id);\n'
        f'      if (res.ok) {rname}State.removeItem(String(id));\n'
        f'    }}\n'
        f'  }}'
        if has_del and pk_field else ''
    )
    goto_import = "  import { goto } from '$app/navigation';\n" if pk_field else ''

    # Generate field type map for validation
    field_types_entries = ', '.join(
        f"'{fname}': '{_field_type_category(all_fields[fname])}'"
        for fname in out_names if fname in all_fields
    )
    field_types_code = f"""
  import {{ isValidFilterValue, normalizeFilterValue, matchFilter, fmtCell, cellTitle, parseFiltersFromUrl, encodeFiltersToUrlParams }} from '$lib/generated/stores/filters';
  import type {{ FieldType }} from '$lib/generated/stores/filters';

  const fieldTypes: Record<string, FieldType> = {{
    {field_types_entries}
  }};

  function initFiltersFromUrl(searchParams: URLSearchParams): Record<string, string> {{
    return parseFiltersFromUrl(searchParams, fieldTypes);
  }}

  function buildUrlWithFilters(currentPath: string, filters: Record<string, string>): string {{
    const url = new URL(currentPath, window.location.origin);

    // Clear existing filter params
    Array.from(url.searchParams.keys())
      .filter(k => k.startsWith('f_'))
      .forEach(k => url.searchParams.delete(k));

    // Add current filters (using shared function)
    const filterParams = encodeFiltersToUrlParams(filters, fieldTypes);
    Object.entries(filterParams).forEach(([key, value]) => {{
      url.searchParams.set(key, value);
    }});

    return url.pathname + url.search;
  }}"""

    return f"""\
<script lang="ts">
  import {{ {rname}State, {rname}Api }} from '$lib/generated/stores/{stem}.svelte.ts';
  import type {{ {iname}Out }} from '$lib/generated/stores/{stem}.svelte.ts';
  import {{ auth }} from '$lib/auth.svelte.ts';
  import {{ untrack }} from 'svelte';
  import {{ goto }} from '$app/navigation';

  let {{ filters = {{}}, embedded = false }}: {{ filters?: Record<string, any>; embedded?: boolean }} = $props();

  const hasFilters = $derived(Object.keys(filters).length > 0);
{field_types_code}
{"" if not pk_field else f"""
  let localFilters = $state<Record<string, string>>({{}});

  // Initialize localFilters from URL or store on mount (using a closure to run once)
  (() => {{
    if (!embedded) {{
      const urlFilters = initFiltersFromUrl(new URLSearchParams(window.location.search));
      if (Object.keys(urlFilters).length > 0) {{
        // URL has priority
        localFilters = urlFilters;
        {rname}State.filters = urlFilters;
      }} else {{
        // Try to restore from store
        const storeFilters = {rname}State.filters;
        if (Object.keys(storeFilters).length > 0) {{
          localFilters = storeFilters;
          // Update URL to reflect store filters
          const newUrl = buildUrlWithFilters(window.location.pathname, storeFilters);
          if (newUrl !== window.location.pathname + window.location.search) {{
            goto(newUrl, {{ replaceState: true, keepFocus: true }});
          }}
        }}
      }}
    }}
  }})();

  function clearAllFilters() {{
    localFilters = {{}};
  }}

  function selectAndNavigate(id: string) {{
    {rname}State.selectedId = id;
    goto(`/ho_bo/{schema_name}/{table_name}/${{id}}`);
  }}

  const displayItems = $derived.by(() => {{
    let items: {iname}Out[] = hasFilters
      ? Array.from({rname}State.byId.values()).filter(item =>
            Object.entries(filters).every(([k, v]) => String((item as any)[k]) === String(v)))
      : {rname}State.items;
    const lf = localFilters;
    if (Object.values(lf).some(v => v))
      items = items.filter(item =>
        Object.entries(lf).every(([k, v]) => matchFilter((item as any)[k], v)));
    const sf = {rname}State.sortField;
    if (sf) {{
      const asc = {rname}State.sortAsc;
      items = [...items].sort((a, b) => {{
        const av = String((a as any)[sf] ?? '');
        const bv = String((b as any)[sf] ?? '');
        return asc ? av.localeCompare(bv) : bv.localeCompare(av);
      }});
    }}
    return items;
  }});
""".rstrip()}{"" if pk_field else f"""
  let localFilters = $state<Record<string, string>>({{}});

  const displayItems = $derived.by(() => {{
    let items: {iname}Out[] = {rname}State.items;
    const lf = localFilters;
    if (Object.values(lf).some(v => v))
      items = items.filter(item =>
        Object.entries(lf).every(([k, v]) => matchFilter((item as any)[k], v)));
    const sf = {rname}State.sortField;
    if (sf) {{
      const asc = {rname}State.sortAsc;
      items = [...items].sort((a, b) => {{
        const av = String((a as any)[sf] ?? '');
        const bv = String((b as any)[sf] ?? '');
        return asc ? av.localeCompare(bv) : bv.localeCompare(av);
      }});
    }}
    return items;
  }});
""".rstrip()}

  let hasMore = $state(true);
  let currentOffset = $state(0);
  let isLoading = $state(false);

  $effect(() => {{
    void auth.token;
    isLoading = true;
    {rname}Api.list(filters).then(result => {{
      hasMore = result.has_more;
      currentOffset = result.offset;
      isLoading = false;
    }});
  }});

  async function loadMore() {{
    if (!hasMore || isLoading) return;
    isLoading = true;
    const result = await {rname}Api.list(filters, currentOffset);
    hasMore = result.has_more;
    currentOffset = result.offset;
    isLoading = false;
  }}

  // Backend filtering with debounce
  let filterDebounceTimer: number | undefined;
  let hadFilters = false;
  $effect(() => {{
    // Track localFilters changes
    const lf = localFilters;

    if (filterDebounceTimer) clearTimeout(filterDebounceTimer);
    filterDebounceTimer = window.setTimeout(() => {{
      // Convert local filters to backend search query (q=col1:val1,col2:val2)
      // Only include valid filters based on field type
      const filterPairs: string[] = [];
      Object.entries(localFilters).forEach(([key, val]) => {{
        if (val && isValidFilterValue(key, val, fieldTypes)) {{
          const normalizedVal = normalizeFilterValue(key, val, fieldTypes);
          filterPairs.push(`${{key}}:${{normalizedVal}}`);
        }}
      }});
      const hasFiltersNow = filterPairs.length > 0;
      // Only trigger if we have filters now, or we had filters before (to clear them)
      if (hasFiltersNow || hadFilters) {{
        hadFilters = hasFiltersNow;
        // Reset state for new filter search
        hasMore = true;
        currentOffset = 0;
        isLoading = true;
        const searchParams = hasFiltersNow ? {{ q: filterPairs.join(',') }} as any : {{}};
        {rname}Api.list(searchParams, 0).then(result => {{
          hasMore = result.has_more;
          currentOffset = result.offset;
          isLoading = false;
        }});
      }}
    }}, 600);
  }});

  // Sync filters to URL and store (with debounce handling)
  let urlSyncTimer: number | undefined;
  $effect(() => {{
    if (embedded) return; // Don't sync URL for embedded components

    // Track localFilters changes
    const lf = localFilters;

    if (urlSyncTimer) clearTimeout(urlSyncTimer);
    urlSyncTimer = window.setTimeout(() => {{
      // Update store with current filters
      {rname}State.filters = lf;

      const newUrl = buildUrlWithFilters(window.location.pathname, lf);

      // Only update if URL actually changed
      if (newUrl !== window.location.pathname + window.location.search) {{
        goto(newUrl, {{ replaceState: true, keepFocus: true }});
      }}
    }}, 650); // Slightly longer than filter debounce to ensure they sync
  }});

  function onIntersect(node: HTMLElement, isLast: boolean) {{
    if (!isLast) return {{ destroy() {{}} }};  // Only observe last element
    const observer = new IntersectionObserver(
      (entries) => {{
        if (entries[0].isIntersecting) {{
          loadMore();
        }}
      }},
      {{ rootMargin: '0px 0px 400px 0px' }}
    );
    observer.observe(node);
    return {{
      destroy() {{ observer.disconnect(); }}
    }};
  }}
{"" if not pk_field else f"""
  // Store handles WS updates; list reacts via $state signals automatically

  // Scroll to selected item when component mounts or items change
  $effect(() => {{
    const selectedId = {rname}State.selectedId;
    const items = displayItems; // Track displayItems changes

    if (selectedId && items.length > 0) {{
      // Use setTimeout to ensure DOM is updated
      setTimeout(() => {{
        const element = document.querySelector(`[data-item-id="${{selectedId}}"]`);
        if (element) {{
          element.scrollIntoView({{ block: 'center', behavior: 'smooth' }});
        }}
      }}, 100);
    }}
  }});
""".rstrip()}
{can_create}{can_delete}{delete_fn}
  let jsonDialog = $state<string | null>(null);
  function showJson(v: unknown): void {{ jsonDialog = JSON.stringify(v, null, 2); }}
</script>

{{#if !embedded}}
<div class="flex justify-between items-center mb-4">
  <h1 class="text-2xl font-bold">{title}</h1>{new_btn}
</div>
{{/if}}

<div class="{{embedded ? '' : 'bg-white shadow-sm rounded-lg overflow-auto max-h-[calc(100vh-10rem)]'}}">
  <table class="w-full border-collapse">
    <thead class="{{embedded ? 'bg-gray-100' : 'bg-gray-100 sticky top-0 z-10 shadow-sm'}}">
      <tr>
      {th_cols}
        {action_th}
      </tr>{filter_row}
    </thead>
    <tbody>
      {{#each displayItems as item, i}}
        <tr use:onIntersect={{i === displayItems.length - 1}} {tr_attrs}>
          {action_td}
        {td_cols}
        </tr>
      {{/each}}
      {{#if isLoading}}
        <tr><td colspan="100" class="text-center py-4 text-gray-500">Loading...</td></tr>
      {{/if}}
    </tbody>
  </table>
</div>

{{#if jsonDialog !== null}}
<!-- svelte-ignore a11y_no_static_element_interactions a11y_click_events_have_key_events -->
<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 cursor-default"
     onclick={{() => jsonDialog = null}}
     onkeydown={{(e) => e.key === 'Escape' && (jsonDialog = null)}}>
  <div role="dialog" aria-modal="true" aria-label="JSON" tabindex="-1"
       class="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 p-6"
       onclick={{(e) => e.stopPropagation()}}
       onkeydown={{(e) => e.stopPropagation()}}>
    <div class="flex justify-between items-center mb-3">
      <h3 class="font-semibold text-gray-800">JSON</h3>
      <button onclick={{() => jsonDialog = null}}
              class="text-gray-400 hover:text-gray-600 text-xl leading-none">✕</button>
    </div>
    <pre class="text-xs bg-gray-50 rounded p-4 overflow-auto max-h-[60vh] whitespace-pre-wrap">{{jsonDialog}}</pre>
  </div>
</div>
{{/if}}
"""


def _list_page(stem: str) -> str:
    return f"""\
<script lang="ts">
  import List from '$lib/generated/components/{stem}/List.svelte';
</script>

<List />
"""


def _admin_layout() -> str:
    return """\
<script lang="ts">
  import { auth } from '$lib/auth.svelte.ts';
  import { goto } from '$app/navigation';
  import { page } from '$app/state';

  let { children } = $props();

  $effect(() => {
    if (!auth.token && page.url.pathname !== '/ho_bo') goto('/ho_bo');
  });
</script>

{#if auth.token || page.url.pathname === '/ho_bo'}{@render children()}{/if}
"""


def _new_page_wrapper(stem: str) -> str:
    return f"""\
<script lang="ts">
  import CreateForm from '$lib/generated/components/{stem}/CreateForm.svelte';
</script>

<CreateForm />
"""


def _detail_page_wrapper(stem: str) -> str:
    return f"""\
<script lang="ts">
  import {{ page }} from '$app/state';
  import DetailView from '$lib/generated/components/{stem}/DetailView.svelte';
</script>

<DetailView id={{page.params.id}} />
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


def _text_fields_js(field_names: list, all_fields: dict) -> str:
    text = [f for f in field_names if _is_text_field(f, all_fields)]
    return ', '.join(f"'{f}'" for f in text)


def _null_map_js(text_fields_var: str = 'textFields') -> str:
    return f'.map(([k, v]) => [k, !{text_fields_var}.has(k) && v === \'\' ? null : v] as [string, unknown])'


def _svelte_form_field(f: str, all_fields: dict, bind_prefix: str = 'form') -> str:
    req      = _is_required(f, all_fields)
    req_attr = ' required' if req else ''
    req_mark = ' <span class="text-red-500">*</span>' if req else ''
    itype    = _input_type(f, all_fields)
    if _is_bool_field(f, all_fields):
        return (
            f'<div class="flex items-center gap-2">\n'
            f'      <input id="f_{f}" type="checkbox" bind:checked={{{bind_prefix}.{f}}}\n'
            f'             class="h-4 w-4 rounded border-gray-300" />\n'
            f'      <label for="f_{f}" class="text-sm font-medium text-gray-700">{f}</label>\n'
            f'    </div>'
        )
    if _is_textarea_field(f, all_fields):
        return (
            f'<div>\n'
            f'      <label for="f_{f}" class="block text-sm font-medium text-gray-700 mb-1">{f}{req_mark}</label>\n'
            f'      <textarea id="f_{f}" bind:value={{{bind_prefix}.{f}}}{req_attr}\n'
            f'               class="w-full border rounded px-3 py-2 text-sm font-mono resize-y min-h-[1rem] [field-sizing:content]"></textarea>\n'
            f'    </div>'
        )
    return (
        f'<div>\n'
        f'      <label for="f_{f}" class="block text-sm font-medium text-gray-700 mb-1">{f}{req_mark}</label>\n'
        f'      <input id="f_{f}" type="{itype}" bind:value={{{bind_prefix}.{f}}}{req_attr}\n'
        f'             class="w-full border rounded px-3 py-2 text-sm" />\n'
        f'    </div>'
    )


def _new_page(
    schema_name: str, table_name: str,
    stem: str, rname: str, iname: str,
    post_in_names: list, all_fields: dict,
    optional_post_fields: frozenset = frozenset(),
) -> str:
    title = _title(schema_name, table_name)
    visible_post = [f for f in post_in_names if not _is_server_generated(f, all_fields)]
    fields_init = ', '.join(
        f'{f}: false' if _is_bool_field(f, all_fields) else f'{f}: ""'
        for f in visible_post
    )
    optional_set_js = ', '.join(f"'{f}'" for f in optional_post_fields)
    text_fields_js  = _text_fields_js(visible_post, all_fields)
    form_fields = '\n    '.join(
        _svelte_form_field(f, all_fields)
        for f in visible_post
    )
    return f"""\
<script lang="ts">
  import {{ {rname}Api, {rname}State }} from '$lib/generated/stores/{stem}.svelte.ts';
  import type {{ {iname}PostIn }} from '$lib/generated/stores/{stem}.svelte.ts';
  import {{ goto }} from '$app/navigation';

  let form = $state<Partial<{iname}PostIn>>({{ {fields_init} }});
  let error = $state('');

  const optionalFields = new Set([{optional_set_js}]);
  const textFields = new Set([{text_fields_js}]);

  async function handleSubmit(e: Event) {{
    e.preventDefault();
    try {{
      const payload = Object.fromEntries(
        Object.entries(form as unknown as Record<string, unknown>)
          .filter(([k, v]) => !optionalFields.has(k) || v !== '')
          {_null_map_js()}
      ) as unknown as {iname}PostIn;
      const res = await {rname}Api.create(payload);
      if (!res.ok) throw new Error(await res.text());
      const created = await res.json();
      {rname}State.setItem(created);
      goto('/ho_bo/{schema_name}/{table_name}');
    }} catch (err: any) {{
      error = err.message;
    }}
  }}
</script>

<div class="max-w-lg mx-auto p-6 bg-white rounded-lg shadow mt-6">
  <h1 class="text-2xl font-bold mb-6">New {title}</h1>
  {{#if error}}<p class="text-red-600 mb-4">{{error}}</p>{{/if}}
  <form onsubmit={{handleSubmit}} class="space-y-4">
    {form_fields}
    <div class="flex gap-3 pt-2">
      <button type="submit"
              class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 text-sm">
        Create
      </button>
      <a href="/ho_bo/{schema_name}/{table_name}"
         class="px-4 py-2 border rounded hover:bg-gray-50 text-sm">Cancel</a>
    </div>
  </form>
</div>
"""


def _fields_component_svelte(
    schema_name: str, table_name: str,
    iname: str, pk_field: str,
    out_names: list, fk_deps: list, all_fields: dict,
) -> str:
    fk_map = {lf: (rs, rt) for lf, rs, rt, _ in fk_deps}

    has_latex = any(
        f not in fk_map and f != pk_field and f in all_fields
        and _field_type_category(all_fields[f]) == 'string'
        for f in out_names
    )
    latex_import = "\n  import { renderLatex } from '$lib/latex.ts';" if has_latex else ''

    def _ro_row(f: str) -> str:
        label = f'<span class="font-medium text-gray-600 w-36 shrink-0">{f}</span>'
        if f == pk_field:
            return (
                f'<div class="flex gap-2 items-baseline">{label}'
                f'<span class="font-mono text-xs text-gray-500 break-all">{{item.{f}}}</span></div>'
            )
        if f in fk_map:
            rs, rt = fk_map[f]
            return (
                f'<div class="flex gap-2 items-baseline">{label}'
                f'<a href="/ho_bo/{rs}/{rt}/{{item.{f}}}"'
                f' class="text-blue-500 hover:underline font-mono text-xs">{{item.{f}}}</a></div>'
            )
        if f in all_fields and _field_type_category(all_fields[f]) == 'string':
            return (
                f'<div class="flex gap-2 items-baseline">{label}'
                f'<span class="text-sm break-all">{{@html renderLatex(String(item.{f} ?? \'\'))}}</span></div>'
            )
        return (
            f'<div class="flex gap-2 items-baseline">{label}'
            f'<span class="text-sm break-all">{{item.{f}}}</span></div>'
        )

    rows = '\n  '.join(_ro_row(f) for f in out_names)

    return f"""\
<script lang="ts">{latex_import}
  import type {{ {iname}Out }} from '$lib/generated/stores/{schema_name}_{table_name}.svelte.ts';

  let {{ item }}: {{ item: {iname}Out }} = $props();
</script>

<div class="space-y-2">
  {rows}
</div>
"""


def _detail_page(
    schema_name: str, table_name: str,
    stem: str, rname: str, iname: str,
    out_names: list, put_in_names: list,
    pk_field: str, all_fields: dict,
    has_put: bool,
    fk_deps: list,
    rev_fk_deps: list,
) -> str:
    title   = _title(schema_name, table_name)
    fk_map    = {local: (rs, rt) for local, rs, rt, _ in fk_deps}

    visible_put = [f for f in put_in_names if not _is_server_generated(f, all_fields)]

    # Edit form fields
    form_fields = '\n    '.join(
        _svelte_form_field(f, all_fields)
        for f in visible_put
    ) if visible_put else ''

    # Form state + edit toggle — populated reactively from item once loaded
    extra_script = ''
    edit_btn     = ''
    edit_section = '\n  <Fields {item} />'

    if has_put and visible_put:
        empty_init  = ', '.join(
            f'{f}: false' if _is_bool_field(f, all_fields) else f'{f}: ""'
            for f in visible_put
        )
        def _effect_assign(f: str) -> str:
            if _is_bool_field(f, all_fields):
                return f'form.{f} = Boolean(item.{f});'
            if _input_type(f, all_fields) == 'datetime-local':
                return f'form.{f} = item.{f} ? String(item.{f}).slice(0, 16) : "";'
            return f'form.{f} = (item.{f} as string) ?? "";'
        effect_body = '\n        '.join(_effect_assign(f) for f in visible_put)
        put_text_fields_js = _text_fields_js(visible_put, all_fields)
        extra_script = (
            f'\n  let editing = $state(false);\n'
            f'  let form = $state({{ {empty_init} }});\n'
            f'  let error = $state(\'\');\n'
            f'  const putTextFields = new Set([{put_text_fields_js}]);\n'
            f'  $effect(() => {{\n'
            f'    if (item) {{\n'
            f'        {effect_body}\n'
            f'    }}\n'
            f'  }});\n'
            f'\n  async function handleUpdate(e: Event) {{\n'
            f'    e.preventDefault();\n'
            f'    try {{\n'
            f'      const putPayload = Object.fromEntries(\n'
            f'        Object.entries(form as unknown as Record<string, unknown>)\n'
            f'          {_null_map_js("putTextFields")}\n'
            f'      ) as unknown as {iname}PutIn;\n'
            f'      const res = await {rname}Api.update(id, putPayload);\n'
            f'      if (!res.ok) throw new Error(await res.text());\n'
            f'      const updated = await res.json();\n'
            f'      {rname}State.setItem(updated);\n'
            f'      editing = false;\n'
            f'      document.querySelector(\'main\')?.scrollTo({{ top: 0, behavior: \'smooth\' }});\n'
            f'    }} catch (err: any) {{\n'
            f'      error = err.message;\n'
            f'    }}\n'
            f'  }}'
        )
        edit_btn = (
            '\n    <button onclick={() => { editing = !editing; error = \'\'; }}'
            '\n            class="text-sm px-3 py-1 border rounded hover:bg-gray-50">'
            '\n      {editing ? \'Cancel\' : \'Edit\'}</button>'
        )
        edit_section = f"""

  {{#if !editing}}
  <Fields {{item}} />
  {{:else}}
  {{#if error}}<p class="text-red-600 mb-4">{{error}}</p>{{/if}}
  <form onsubmit={{handleUpdate}} class="space-y-4">
    {form_fields}
    <div class="flex gap-3 pt-2">
      <button type="submit"
              class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 text-sm">
        Update
      </button>
      <button type="button" onclick={{() => {{ editing = false; }}}}
              class="px-4 py-2 border rounded hover:bg-gray-50 text-sm">Cancel</button>
    </div>
  </form>
  {{/if}}"""

    map_key       = f'{schema_name}/{table_name}'
    put_in_import = f', {iname}PutIn' if has_put else ''
    can_edit      = f"\n  const canEdit = $derived(!!auth.access['{map_key}']?.PUT);" if has_put else ''
    edit_btn_wrap = (
        f'\n      {{#if canEdit}}{edit_btn}\n      {{/if}}'
        if has_put and visible_put else ''
    )

    # Forward FK reference imports, states, effects, sections
    def _fk_ref_imports(deps: list) -> str:
        lines = []
        seen: set[str] = {stem}  # skip self-referential FK and deduplicate
        for _, rs, rt, _ in deps:
            s = f'{rs}_{rt}'
            if s in seen:
                continue
            seen.add(s)
            rn = _rname(rs, rt)
            cn = _cname(rs, rt)
            lines.append(f"  import {{ {rn}State, {rn}Api }} from '$lib/generated/stores/{s}.svelte.ts';")
            lines.append(f"  import {cn}Fields from '$lib/generated/components/{s}/Fields.svelte';")
        return ('\n' + '\n'.join(lines)) if lines else ''

    def _lf_ref_name(lf: str) -> str:
        """user_fk → userFkRef  (always unique — keyed on local field, not remote table)"""
        parts = lf.split('_')
        return parts[0] + ''.join(p.capitalize() for p in parts[1:]) + 'Ref'

    def _fk_ref_states(deps: list) -> str:
        lines = []
        for lf, rs, rt, _ in deps:
            rn = _rname(rs, rt)
            lines.append(
                f"  let {_lf_ref_name(lf)} = $derived(item?.{lf} ? {rn}State.byId.get(String(item.{lf})) ?? null : null);"
            )
        return ('\n' + '\n'.join(lines)) if lines else ''

    def _fk_ref_effects(deps: list) -> str:
        blocks = []
        for lf, rs, rt, _ in deps:
            rn = _rname(rs, rt)
            blocks.append(
                f'  $effect(() => {{\n'
                f'    if (!item?.{lf}) return;\n'
                f'    const _url = {rn}Api.getUrl(item.{lf});\n'
                f'    if (!auth.fetchedRoutes.has(_url))\n'
                f'      {rn}Api.get(item.{lf}).then(r => r.ok ? r.json() : null)\n'
                f'               .then(d => {{ if (d) {rn}State.setItem(d); }});\n'
                f'  }});'
            )
        return ('\n' + '\n'.join(blocks)) if blocks else ''

    def _fk_ws_effects(deps: list) -> str:
        blocks = []
        for lf, rs, rt, _ in deps:
            rn = _rname(rs, rt)
            fk_map_key = f'{rs}/{rt}'
            blocks.append(
                f'  $effect(() => {{\n'
                f'    const ev = auth.lastEvent;\n'
                f'    const v = item?.{lf};\n'
                f"    if (ev?.resource === '{fk_map_key}' && v && String(ev.id) === String(v) && ev.event !== 'delete')\n"
                f'      untrack(() => {rn}Api.refresh(v).then(r => r.ok ? r.json() : null)\n'
                f'               .then(d => {{ if (d) {rn}State.setItem(d); }}));\n'
                f'  }});'
            )
        return ('\n' + '\n'.join(blocks)) if blocks else ''

    def _fk_ref_section(lf: str, rs: str, rt: str, remote_pk: str) -> str:
        lf_ref    = _lf_ref_name(lf)
        is_self   = (rs == schema_name and rt == table_name)
        fk_fields = 'Fields' if is_self else f'{_cname(rs, rt)}Fields'
        return (
            f'\n{{#if {lf_ref}}}\n'
            f'<div class="mt-4 p-6 bg-white rounded-lg shadow">\n'
            f'  <div class="flex justify-between items-center mb-3">\n'
            f'    <h2 class="text-lg font-semibold">{_title(rs, rt)}</h2>\n'
            f'    <a href="/ho_bo/{rs}/{rt}/{{{lf_ref}.{remote_pk}}}"'
            f' class="text-sm text-blue-600 hover:underline">→</a>\n'
            f'  </div>\n'
            f'  <{fk_fields} item={{{lf_ref}}} />\n'
            f'</div>\n'
            f'{{/if}}'
        )

    fk_imports  = _fk_ref_imports(fk_deps)
    fk_states   = _fk_ref_states(fk_deps)
    fk_effects  = _fk_ref_effects(fk_deps)
    fk_sections = '\n'.join(_fk_ref_section(*d) for d in fk_deps)

    # Reverse FK imports and sections
    rev_imports = '\n'.join(
        f"  import {_cname(rs, rt)}List from '$lib/generated/components/{rs}_{rt}/List.svelte';"
        for rs, rt, _ in rev_fk_deps
    )
    if rev_imports:
        rev_imports = '\n' + rev_imports

    def _rev_section(rs: str, rt: str, fk_field: str) -> str:
        cn = _cname(rs, rt)
        return (
            f'\n<div class="mt-4 bg-white rounded-lg shadow overflow-hidden">\n'
            f'  <div class="px-6 pt-5 pb-3 flex items-center justify-between">\n'
            f'    <h2 class="text-lg font-semibold">{_title(rs, rt)}</h2>\n'
            f'    <span class="flex items-center gap-1 text-xs text-gray-400">\n'
            f'      <svg class="w-3.5 h-3.5 shrink-0" viewBox="0 0 20 20" fill="currentColor">\n'
            f'        <path fill-rule="evenodd" d="M3 3a1 1 0 011-1h12a1 1 0 011 1v3a1 1 0 01-.293.707L13 10.414V15a1 1 0 01-.553.894l-4 2A1 1 0 017 17v-6.586L3.293 6.707A1 1 0 013 6V3z" clip-rule="evenodd"/>\n'
            f'      </svg>\n'
            f'      {fk_field} = {{item?.{pk_field} ?? \'\'}}\n'
            f'    </span>\n'
            f'  </div>\n'
            f'  {{#if item}}\n'
            f'    <{cn}List filters={{{{ {fk_field}: item.{pk_field} }}}} embedded />\n'
            f'  {{/if}}\n'
            f'</div>'
        )

    rev_sections = '\n'.join(_rev_section(rs, rt, fk) for rs, rt, fk in rev_fk_deps)

    right_col = ''
    if fk_deps:
        right_col += '\n<p class="mt-4 px-1 text-xs font-semibold uppercase tracking-wide text-gray-400">↗ Direct references</p>'
        right_col += fk_sections
    if rev_fk_deps:
        if fk_deps:
            right_col += '\n<hr class="my-6 border-gray-200">'
        right_col += '\n<p class="mt-4 px-1 text-xs font-semibold uppercase tracking-wide text-gray-400">↙ Related</p>'
        right_col += '\n' + rev_sections

    return f"""\
<script lang="ts">
  import {{ {rname}State, {rname}Api }} from '$lib/generated/stores/{stem}.svelte.ts';
  import type {{ {iname}Out{put_in_import} }} from '$lib/generated/stores/{stem}.svelte.ts';
  import {{ goto }} from '$app/navigation';
  import {{ auth }} from '$lib/auth.svelte.ts';
  import {{ untrack }} from 'svelte';
  import Fields from '$lib/generated/components/{stem}/Fields.svelte';{fk_imports}{rev_imports}

  let {{ id }}: {{ id: string }} = $props();
  let item = $derived({rname}State.byId.get(id) ?? null);
{fk_states}
  $effect(() => {{
    void auth.token;
    if (!item) untrack(() => {rname}Api.get(id).then(r => r.ok ? r.json() : null)
                .then(d => {{ if (d) {rname}State.setItem(d); }}));
  }});

  $effect(() => {{
    const ev = auth.lastEvent;
    if (ev?.resource === '{map_key}' && String(ev.id) === id && ev.event === 'delete')
      goto('/ho_bo/{schema_name}/{table_name}');
  }});
{fk_effects}{can_edit}{extra_script}
</script>

<div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6 px-4 lg:h-[calc(100vh-4rem)] lg:overflow-hidden">
  <div class="min-w-0 lg:overflow-y-auto lg:pr-1">
    {{#if item}}
    <div class="p-6 bg-white rounded-lg shadow">
      <div class="flex justify-between items-start mb-6">
        <h1 class="text-2xl font-bold">{title}</h1>
        <div class="flex gap-3 items-center">
{edit_btn_wrap}
          <a href="/ho_bo/{schema_name}/{table_name}" class="text-sm text-gray-500 hover:underline">← Back</a>
        </div>
      </div>

      <div class="flex gap-2 items-baseline mb-4">
        <span class="font-medium text-gray-600 w-36 shrink-0">{pk_field}</span>
        <span class="font-mono text-xs text-gray-500 break-all">{{item.{pk_field}}}</span>
      </div>
      {edit_section}
    </div>
    {{/if}}
  </div>
  <div class="min-w-0 lg:overflow-y-auto lg:pr-1">
    {right_col}
  </div>
</div>
"""


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

class SvelteAppGenerator(StoreGenerator):

    def generate(self, classes, api_version, output_dir: Path) -> None:
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True)

        version_prefix = f'/v{api_version}' if api_version is not None else ''
        project_name = output_dir.name

        # --- static files ---
        self._write(output_dir / 'package.json',
                    _PACKAGE_JSON.format(project_name=project_name))
        self._write(output_dir / 'svelte.config.js',    _SVELTE_CONFIG)
        self._write(output_dir / 'vite.config.ts',
                    _VITE_CONFIG.format(version_prefix=version_prefix or '/api'))
        self._write(output_dir / 'tsconfig.json',        _TSCONFIG)
        self._write(output_dir / 'tailwind.config.js',  _TAILWIND_CONFIG)
        self._write(output_dir / 'postcss.config.js',   _POSTCSS_CONFIG)
        self._write(output_dir / 'src' / 'app.html',    _APP_HTML)
        self._write(output_dir / 'src' / 'app.css',     _APP_CSS)

        # --- stores (reuse SvelteGenerator) ---
        stores_dir = output_dir / 'src' / 'lib' / 'generated' / 'stores'
        SvelteGenerator().generate(classes, api_version, stores_dir)

        # --- stateRegistry + auth store + WS env var ---
        self._write(output_dir / 'src' / 'lib' / 'latex.ts', _LATEX_TS)
        self._write(output_dir / 'src' / 'lib' / 'stateRegistry.ts',
            "const _fns: Array<() => void> = [];\n"
            "export const registerClear = (fn: () => void): void => { _fns.push(fn); };\n"
            "export const clearAllStates = (): void => { _fns.forEach(fn => fn()); };\n"
        )
        self._write(output_dir / 'src' / 'lib' / 'auth.svelte.ts', _auth_store(version_prefix))
        env_local = output_dir / '.env.local'
        if not env_local.exists():
            self._write(env_local, 'VITE_WS_BASE=http://localhost:8000\n')

        # Pass 1: identify all resources that expose CRUD_ACCESS
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

        # Pass 2: build per-resource metadata (needs complete crud_resources for fk_deps)
        resources = []
        for relation, mod in raw:
            crud_access  = getattr(mod, 'CRUD_ACCESS', None) or {'GET': {}, 'POST': {}, 'PUT': {}, 'DELETE': {}}
            api_excluded = getattr(mod, 'API_EXCLUDED_FIELDS', [])
            schema_name  = relation._t_fqrn[1]
            table_name   = relation._t_fqrn[2]
            inst         = _instance(relation)
            all_fields   = getattr(inst, '_ho_fields', {})
            all_names    = list(all_fields.keys())
            pk_cols      = _pk_info(relation)
            pk_info      = pk_cols
            pk_field     = pk_cols[0][0] if pk_cols else None
            iname        = self.interface_name(schema_name, table_name)
            rname        = self.resource_name(schema_name, table_name)
            stem         = f'{schema_name}_{table_name}'
            map_key      = f'{schema_name}/{table_name}'

            out_names = _gen_out_fields(crud_access, 'GET', api_excluded, all_names)
            if not out_names:
                out_names = [f for f in all_names if f not in api_excluded]

            has_post = 'POST' in crud_access and bool(pk_info)
            has_put  = 'PUT'  in crud_access and bool(pk_info)
            has_del  = 'DELETE' in crud_access and bool(pk_info)

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
            post_in_names = _gen_in_fields(
                crud_access, 'POST', pk_field, api_excluded, all_names, pk_has_default
            ) if has_post else []
            if has_post and not post_in_names:
                post_in_names = _non_pk
            put_in_names = _gen_in_fields(
                crud_access, 'PUT', pk_field, api_excluded, all_names
            ) if has_put else []
            if has_put and not put_in_names:
                put_in_names = _non_pk
            optional_post_fields = frozenset(f for f in post_in_names if f in fields_with_defaults)

            fk_deps     = self._fk_deps(inst, out_names, crud_resources)
            rev_fk_deps = self._reverse_fk_deps(inst, pk_field, crud_resources)

            resources.append((
                schema_name, table_name, stem, rname, iname,
                out_names, pk_info, pk_field, all_fields,
                has_post, has_put, has_del,
                post_in_names, put_in_names, map_key, crud_access, fk_deps, rev_fk_deps,
                optional_post_fields,
            ))

        # --- static assets ---
        assets_src = Path(__file__).parent.parent / 'assets'
        static_dir = output_dir / 'static'
        static_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(assets_src / 'logo.png', static_dir / 'logo.png')

        # --- layout + home ---
        routes_dir     = output_dir / 'src' / 'routes'
        components_dir = output_dir / 'src' / 'lib' / 'generated' / 'components'
        # Root layout is minimal — home page renders without nav
        self._write(routes_dir / '+layout.svelte',
                    '<script>\n  import \'../app.css\';\n  let { children } = $props();\n</script>\n{@render children()}\n')
        # (nav) group provides the sidebar layout for all other pages
        self._write(routes_dir / '(nav)' / '+layout.svelte', _layout(resources))
        self._write(routes_dir / '(nav)' / 'ho_bo' / '+layout.svelte', _admin_layout())
        first_route = (
            f'/ho_bo/{resources[0][0]}/{resources[0][1]}' if resources else '/ho_bo'
        )
        self._write(routes_dir / '+page.svelte', _home_page(), once=True)
        self._write(routes_dir / '(nav)' / 'ho_bo' / '+page.svelte', _login_page(version_prefix))
        self._write(routes_dir / '(nav)' / 'login'  / '+page.svelte', _login_page(version_prefix))
        self._write(routes_dir / '(nav)' / 'access' / '+page.svelte', _access_page(version_prefix))

        # --- per-resource components + routes ---
        for (schema_name, table_name, stem, rname, iname,
             out_names, pk_info, pk_field, all_fields,
             has_post, has_put, has_del,
             post_in_names, put_in_names, map_key, crud_access, fk_deps, rev_fk_deps,
             optional_post_fields) in resources:

            comp_dir = components_dir / stem
            res_dir  = routes_dir / '(nav)' / 'ho_bo' / schema_name / table_name

            # List component + thin page wrapper
            self._write(
                comp_dir / 'List.svelte',
                _list_component(schema_name, table_name, stem, rname, iname,
                                out_names, pk_info, has_post, has_del, map_key, fk_deps, all_fields),
            )
            self._write(res_dir / '+page.svelte', _list_page(stem))

            # CreateForm component + thin page wrapper
            if has_post:
                self._write(
                    comp_dir / 'CreateForm.svelte',
                    _new_page(schema_name, table_name, stem, rname, iname,
                              post_in_names, all_fields, optional_post_fields),
                )
                self._write(res_dir / 'new' / '+page.svelte', _new_page_wrapper(stem))

            # DetailView component + thin page wrapper
            if pk_info and 'GET' in crud_access:
                self._write(
                    comp_dir / 'Fields.svelte',
                    _fields_component_svelte(schema_name, table_name, iname,
                                             pk_field, out_names, fk_deps, all_fields),
                )
                self._write(
                    comp_dir / 'DetailView.svelte',
                    _detail_page(schema_name, table_name, stem, rname, iname,
                                 out_names, put_in_names, pk_field, all_fields,
                                 has_put, fk_deps, rev_fk_deps),
                )
                self._write(res_dir / '[id]' / '+page.svelte', _detail_page_wrapper(stem))

        print(f'\nSvelteKit app generated in {output_dir}')
        print('Next steps:')
        print(f'  cd {output_dir}')
        print('  npm install')
        print('  npm run dev')

    def _write(self, path: Path, content: str, *, once: bool = False) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if once and path.exists():
            print(f'  {path}  (skipped — developer-owned)')
            return
        path.write_text(content, encoding='utf-8')
        print(f'  {path}')
