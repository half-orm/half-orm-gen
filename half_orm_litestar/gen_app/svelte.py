"""
SvelteKit 5 POC application generator.

Produces a throwaway SvelteKit app (Tailwind + TypeScript + Svelte 5 runes)
with one list/detail/create page per CRUD_ACCESS resource.
"""

import importlib
import shutil
from pathlib import Path

from half_orm_litestar.crud_routes import (
    _gen_out_fields,
    _gen_in_fields,
    _pk_info,
    _simple_pk,
    _instance,
    _py_type_str,
)
from half_orm_litestar.gen_store.svelte import SvelteGenerator
from half_orm_litestar.gen_store.base import StoreGenerator


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
@tailwind base;
@tailwind components;
@tailwind utilities;
"""

def _auth_store(version_prefix: str) -> str:
    return f"""\
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
    goto('/');
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

_HOME_PAGE = """\
<script lang="ts">
  import {{ goto }} from '$app/navigation';
  import {{ onMount }} from 'svelte';
  onMount(() => goto('{first_route}'));
</script>
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
        f'{{ href: "/{sn}/{tn}", label: "{_title(sn, tn)}" }}'
        for sn, tn, *_ in resources
    )
    return f"""\
<script lang="ts">
  import '../app.css';
  import {{ auth }} from '$lib/auth.svelte.ts';

  let {{ children }} = $props();
  let navFilter = $state('');
  const navItems = [
    {nav_items_js}
  ];
  const filteredNav = $derived(
    navFilter
      ? navItems.filter(i => i.label.toLowerCase().includes(navFilter.toLowerCase()))
      : navItems
  );
</script>

<div class="h-screen flex bg-gray-50 overflow-hidden">
  <aside class="w-56 shrink-0 bg-white border-r flex flex-col">
    <div class="px-4 py-4 border-b">
      <span class="font-bold text-gray-800">API Browser</span>
    </div>
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
    <div class="px-2 py-3 border-t">
      <a href="/access"
         class="block px-3 py-2 rounded hover:bg-gray-100">
        <div class="text-xs text-gray-400 mb-0.5">Role</div>
        <div class="text-sm font-medium {{auth.token ? 'text-blue-700' : 'text-gray-400'}}">
          {{auth.token ?? 'public'}}
        </div>
      </a>
    </div>
  </aside>
  <main class="flex-1 overflow-y-auto p-6">
    {{@render children()}}
  </main>
</div>
"""


def _cname(schema_name: str, table_name: str) -> str:
    """PascalCase component/interface name — e.g. BlogComment"""
    return ''.join(p.capitalize() for p in f'{schema_name}_{table_name}'.split('_'))


def _rname(schema_name: str, table_name: str) -> str:
    """camelCase resource name — e.g. blogComment"""
    parts = schema_name.split('_') + table_name.split('_')
    return parts[0].lower() + ''.join(p.capitalize() for p in parts[1:])


def _list_component(
    schema_name: str, table_name: str,
    stem: str, rname: str, iname: str,
    out_names: list, pk_info: list,
    has_post: bool, has_del: bool,
    map_key: str,
    fk_deps: list,
) -> str:
    pk_field = pk_info[0][0] if pk_info else None
    if len(pk_info) == 1:
        pk_item_expr = f'item.{pk_field}'
    elif len(pk_info) > 1:
        pk_item_expr = '[' + ', '.join(f'item.{f}' for f, _, _ in pk_info) + '].map(String).join("::")'
    else:
        pk_item_expr = None
    title    = _title(schema_name, table_name)
    fk_map   = {local: (rs, rt) for local, rs, rt, _ in fk_deps}

    def _sort_th(f: str) -> str:
        toggle = (
            f"() => {{ if (sortField === '{f}') sortAsc = !sortAsc;"
            f" else {{ sortField = '{f}'; sortAsc = true; }} }}"
        )
        indicator = f"{{#if sortField === '{f}'}}{{sortAsc ? '↑' : '↓'}}{{/if}}"
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
        f'<input bind:value={{localFilters[\'{f}\']}} placeholder="…"'
        f' class="w-full text-xs border rounded px-2 py-1 font-normal" /></th>'
        for f in out_names
    )
    action_filter_th = '<th></th>' if has_del and pk_field else ''
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
                f'<a href="/{rs}/{rt}/{{item.{f}}}"'
                f' onclick={{(e) => {{ e.preventDefault(); e.stopPropagation(); goto(`/{rs}/{rt}/${{item.{f}}}`); }}}}'
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
        tr_open = (
            f'<tr class="border-t hover:bg-gray-50 cursor-pointer"'
            f' onclick={{() => goto(`/{schema_name}/{table_name}/${{{pk_item_expr}}}`)}}'
            f'>'
        )
    else:
        tr_open = '<tr class="border-t hover:bg-gray-50">'

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
        f'    <a href="/{schema_name}/{table_name}/new"\n'
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

    return f"""\
<script lang="ts">
  import {{ {rname}State, {rname}Api }} from '$lib/stores/{stem}.svelte.ts';
  import type {{ {iname}Out }} from '$lib/stores/{stem}.svelte.ts';
  import {{ auth }} from '$lib/auth.svelte.ts';
  import {{ untrack }} from 'svelte';
{goto_import}
  let {{ filters = {{}}, embedded = false }}: {{ filters?: Record<string, any>; embedded?: boolean }} = $props();

  const hasFilters = $derived(Object.keys(filters).length > 0);
{"" if not pk_field else f"""
  let localFilters = $state<Record<string, string>>({{}});
  let sortField    = $state<string | null>(null);
  let sortAsc      = $state(true);

  const displayItems = $derived.by(() => {{
    let items: {iname}Out[] = hasFilters
      ? Array.from({rname}State.byId.values()).filter(item =>
            Object.entries(filters).every(([k, v]) => String((item as any)[k]) === String(v)))
      : {rname}State.items;
    const lf = localFilters;
    if (Object.values(lf).some(v => v))
      items = items.filter(item =>
        Object.entries(lf).every(([k, v]) =>
          !v || String((item as any)[k] ?? '').toLowerCase().includes(v.toLowerCase())));
    const sf = sortField;
    if (sf) {{
      const asc = sortAsc;
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
  let sortField    = $state<string | null>(null);
  let sortAsc      = $state(true);

  const displayItems = $derived.by(() => {{
    let items: {iname}Out[] = {rname}State.items;
    const lf = localFilters;
    if (Object.values(lf).some(v => v))
      items = items.filter(item =>
        Object.entries(lf).every(([k, v]) =>
          !v || String((item as any)[k] ?? '').toLowerCase().includes(v.toLowerCase())));
    const sf = sortField;
    if (sf) {{
      const asc = sortAsc;
      items = [...items].sort((a, b) => {{
        const av = String((a as any)[sf] ?? '');
        const bv = String((b as any)[sf] ?? '');
        return asc ? av.localeCompare(bv) : bv.localeCompare(av);
      }});
    }}
    return items;
  }});
""".rstrip()}

  $effect(() => {{
    const url = {rname}Api.listUrl(filters);
    if (!auth.fetchedRoutes.has(url)) {{
      const filtered = hasFilters;
      {rname}Api.list(filters).then(r => r.ok ? r.json() : []).then(d => {{
        if (filtered) {rname}State.mergeItems(d);
        else {rname}State.setItems(d);
      }});
    }}
  }});
{"" if not pk_field else f"""
  $effect(() => {{
    const ev = auth.lastEvent;
    if (!ev || ev.resource !== '{map_key}') return;
    if (ev.event === 'delete') {{
      untrack(() => {rname}State.removeItem(String(ev.id)));
    }} else {{
      untrack(() => {rname}Api.get(ev.id)
        .then(r => r.ok ? r.json() : null)
        .then(d => {{ if (d) {rname}State.setItem(d); }}));
    }}
  }});
""".rstrip()}
{can_create}{can_delete}{delete_fn}
  let jsonDialog = $state<string | null>(null);
  function showJson(v: unknown): void {{ jsonDialog = JSON.stringify(v, null, 2); }}
  function fmtCell(v: unknown): string {{
    if (v == null) return '';
    if (Array.isArray(v)) return `JSON [${{v.length}}]`;
    if (typeof v === 'object') return 'JSON {{…}}';
    const s = String(v);
    return /^[0-9a-f]{{8}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{12}}$/i.test(s)
      ? s.slice(0, 8) + '…' : s;
  }}
  function cellTitle(v: unknown): string {{
    if (v == null || typeof v === 'object') return '';
    return String(v);
  }}
</script>

{{#if !embedded}}
<div class="flex justify-between items-center mb-4">
  <h1 class="text-2xl font-bold">{title}</h1>{new_btn}
</div>
{{/if}}

<div class="{{embedded ? '' : 'bg-white shadow-sm rounded-lg overflow-hidden'}}">
  <table class="w-full border-collapse">
    <thead class="bg-gray-100">
      <tr>
      {th_cols}
        {action_th}
      </tr>{filter_row}
    </thead>
    <tbody>
      {{#each displayItems as item}}
        {tr_open}
          {action_td}
        {td_cols}
        </tr>
      {{/each}}
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
  import List from '$lib/components/{stem}_list.svelte';
</script>

<List />
"""


def _is_bool_field(f: str, all_fields: dict) -> bool:
    return f in all_fields and _py_type_str(all_fields[f].py_type) == 'bool'


def _is_text_field(f: str, all_fields: dict) -> bool:
    return f in all_fields and _py_type_str(all_fields[f].py_type) == 'str'


def _is_required(f: str, all_fields: dict) -> bool:
    fo = all_fields.get(f)
    return bool(fo and fo.is_not_null() and fo.has_default_value is None)


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
    fields_init = ', '.join(
        f'{f}: false' if _is_bool_field(f, all_fields) else f'{f}: ""'
        for f in post_in_names
    )
    optional_set_js = ', '.join(f"'{f}'" for f in optional_post_fields)
    text_fields_js  = _text_fields_js(post_in_names, all_fields)
    form_fields = '\n    '.join(
        _svelte_form_field(f, all_fields)
        for f in post_in_names
    )
    return f"""\
<script lang="ts">
  import {{ {rname}Api, {rname}State }} from '$lib/stores/{stem}.svelte.ts';
  import type {{ {iname}PostIn }} from '$lib/stores/{stem}.svelte.ts';
  import {{ goto }} from '$app/navigation';

  let form = $state<{iname}PostIn>({{ {fields_init} }});
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
      goto('/{schema_name}/{table_name}');
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
      <a href="/{schema_name}/{table_name}"
         class="px-4 py-2 border rounded hover:bg-gray-50 text-sm">Cancel</a>
    </div>
  </form>
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
    read_only = [f for f in out_names if f != pk_field]

    # Read-only fields — FK fields rendered as links
    def _ro_row(f: str) -> str:
        label = f'<span class="font-medium text-gray-600 w-36 shrink-0">{f}</span>'
        if f in fk_map:
            rs, rt = fk_map[f]
            value = (
                f'<a href="/{rs}/{rt}/{{item.{f}}}"'
                f' class="text-blue-500 hover:underline font-mono text-xs">{{item.{f}}}</a>'
            )
        else:
            value = f'<span class="text-sm break-all">{{item.{f}}}</span>'
        return f'<div class="flex gap-2 items-baseline">{label}{value}</div>'

    ro_fields = '\n    '.join(_ro_row(f) for f in read_only) if read_only else ''

    # Edit form fields
    form_fields = '\n    '.join(
        _svelte_form_field(f, all_fields)
        for f in put_in_names
    ) if put_in_names else ''

    # Form state + edit toggle — populated reactively from item once loaded
    extra_script = ''
    edit_btn     = ''
    edit_section = ''

    if has_put and put_in_names:
        empty_init  = ', '.join(
            f'{f}: false' if _is_bool_field(f, all_fields) else f'{f}: ""'
            for f in put_in_names
        )
        def _effect_assign(f: str) -> str:
            if _is_bool_field(f, all_fields):
                return f'form.{f} = Boolean(item.{f});'
            if _input_type(f, all_fields) == 'datetime-local':
                return f'form.{f} = item.{f} ? String(item.{f}).slice(0, 16) : "";'
            return f'form.{f} = (item.{f} as string) ?? "";'
        effect_body = '\n        '.join(_effect_assign(f) for f in put_in_names)
        put_text_fields_js = _text_fields_js(put_in_names, all_fields)
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
            f'      const res = await {rname}Api.update(page.params.id, putPayload);\n'
            f'      if (!res.ok) throw new Error(await res.text());\n'
            f'      const updated = await res.json();\n'
            f'      {rname}State.setItem(updated);\n'
            f'      editing = false;\n'
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

  {{#if editing}}
  <div class="mt-6 pt-6 border-t">
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
  </div>
  {{/if}}"""

    map_key       = f'{schema_name}/{table_name}'
    put_in_import = f', {iname}PutIn' if has_put else ''
    can_edit      = f"\n  const canEdit = $derived(!!auth.access['{map_key}']?.PUT);" if has_put else ''
    edit_btn_wrap = (
        f'\n      {{#if canEdit}}{edit_btn}\n      {{/if}}'
        if has_put and put_in_names else ''
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
            lines.append(f"  import {{ {rn}State, {rn}Api }} from '$lib/stores/{s}.svelte.ts';")
        return ('\n' + '\n'.join(lines)) if lines else ''

    def _lf_ref_name(lf: str) -> str:
        """user_fk → userFkRef  (always unique — keyed on local field, not remote table)"""
        parts = lf.split('_')
        return parts[0] + ''.join(p.capitalize() for p in parts[1:]) + 'Ref'

    def _fk_ref_states(deps: list) -> str:
        lines = [
            f"  let {_lf_ref_name(lf)} = $state<{_cname(rs, rt)}Out | null>(null);"
            for lf, rs, rt, _ in deps
        ]
        return ('\n' + '\n'.join(lines)) if lines else ''

    def _fk_ref_effects(deps: list) -> str:
        blocks = []
        for lf, rs, rt, _ in deps:
            rn     = _rname(rs, rt)
            lf_ref = _lf_ref_name(lf)
            blocks.append(
                f'  $effect(() => {{\n'
                f'    if (!item?.{lf}) return;\n'
                f'    const _url = {rn}Api.getUrl(item.{lf});\n'
                f'    if (auth.fetchedRoutes.has(_url)) {{\n'
                f'      {lf_ref} = {rn}State.byId.get(String(item.{lf})) ?? null;\n'
                f'    }} else {{\n'
                f'      {rn}Api.get(item.{lf}).then(r => r.ok ? r.json() : null)\n'
                f'                .then(d => {{ if (d) {{ {rn}State.setItem(d); {lf_ref} = d; }} }});\n'
                f'    }}\n'
                f'  }});'
            )
        return ('\n' + '\n'.join(blocks)) if blocks else ''

    def _fk_ref_section(lf: str, rs: str, rt: str, remote_pk: str) -> str:
        rn     = _rname(rs, rt)
        lf_ref = _lf_ref_name(lf)
        return (
            f'\n{{#if {lf_ref}}}\n'
            f'<div class="mt-4 p-6 bg-white rounded-lg shadow">\n'
            f'  <div class="flex justify-between items-center mb-3">\n'
            f'    <h2 class="text-lg font-semibold">{_title(rs, rt)}</h2>\n'
            f'    <a href="/{rs}/{rt}/{{{lf_ref}.{remote_pk}}}"'
            f' class="text-sm text-blue-600 hover:underline">→</a>\n'
            f'  </div>\n'
            f'  <div class="space-y-1">\n'
            f'    {{#each Object.entries({lf_ref}) as [k, v]}}\n'
            f'      <div class="flex gap-2 items-baseline">\n'
            f'        <span class="font-medium text-gray-600 w-36 shrink-0 text-sm">{{k}}</span>\n'
            f'        <span class="text-sm break-all">{{String(v ?? \'\')}}</span>\n'
            f'      </div>\n'
            f'    {{/each}}\n'
            f'  </div>\n'
            f'</div>\n'
            f'{{/if}}'
        )

    fk_imports   = _fk_ref_imports(fk_deps)
    fk_states    = _fk_ref_states(fk_deps)
    fk_effects   = _fk_ref_effects(fk_deps)
    fk_sections  = '\n'.join(_fk_ref_section(*d) for d in fk_deps)

    # Reverse FK imports and sections
    rev_imports = '\n'.join(
        f"  import {_cname(rs, rt)}List from '$lib/components/{rs}_{rt}_list.svelte';"
        for rs, rt, _ in rev_fk_deps
    )
    if rev_imports:
        rev_imports = '\n' + rev_imports

    def _rev_section(rs: str, rt: str, fk_field: str) -> str:
        cn = _cname(rs, rt)
        return (
            f'\n<div class="mt-4 bg-white rounded-lg shadow overflow-hidden">\n'
            f'  <div class="px-6 pt-5 pb-3">\n'
            f'    <h2 class="text-lg font-semibold">{_title(rs, rt)}</h2>\n'
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
  import {{ {rname}State, {rname}Api }} from '$lib/stores/{stem}.svelte.ts';
  import type {{ {iname}Out{put_in_import} }} from '$lib/stores/{stem}.svelte.ts';
  import {{ goto }} from '$app/navigation';
  import {{ page }} from '$app/state';
  import {{ auth }} from '$lib/auth.svelte.ts';
  import {{ untrack }} from 'svelte';{fk_imports}{rev_imports}

  let item      = $state<{iname}Out | null>({rname}State.byId.get(page.params.id) ?? null);
  let _lastToken = auth.token;
{fk_states}
  $effect(() => {{
    const t = auth.token;
    if (t !== _lastToken) {{ _lastToken = t; item = null; }}
    if (!item)
      {rname}Api.get(page.params.id).then(r => r.ok ? r.json() : null)
                .then(d => {{ if (d) {{ item = d; {rname}State.setItem(d); }} }});
  }});

  $effect(() => {{
    const ev = auth.lastEvent;
    if (ev?.resource === '{map_key}' && String(ev.id) === page.params.id) {{
      if (ev.event === 'delete') goto('/{schema_name}/{table_name}');
      else untrack(() => {rname}Api.get(page.params.id).then(r => r.ok ? r.json() : null)
                .then(d => {{ if (d) {{ item = d; {rname}State.setItem(d); }} }}));
    }}
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
          <a href="/{schema_name}/{table_name}" class="text-sm text-gray-500 hover:underline">← Back</a>
        </div>
      </div>

      <div class="space-y-2 mb-4">
        <div class="flex gap-2 items-baseline">
          <span class="font-medium text-gray-600 w-36 shrink-0">{pk_field}</span>
          <span class="font-mono text-xs text-gray-500 break-all">{{item.{pk_field}}}</span>
        </div>
        {ro_fields}
      </div>{edit_section}
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
        stores_dir = output_dir / 'src' / 'lib' / 'stores'
        SvelteGenerator().generate(classes, api_version, stores_dir)

        # --- stateRegistry + auth store + WS env var ---
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

        # --- layout + home ---
        routes_dir = output_dir / 'src' / 'routes'
        self._write(routes_dir / '+layout.svelte', _layout(resources))
        first_route = (
            f'/{resources[0][0]}/{resources[0][1]}' if resources else '/'
        )
        self._write(routes_dir / '+page.svelte',
                    _HOME_PAGE.format(first_route=first_route))
        self._write(routes_dir / 'login'  / '+page.svelte', _login_page(version_prefix))
        self._write(routes_dir / 'access' / '+page.svelte', _access_page(version_prefix))

        # --- reusable list components ---
        components_dir = output_dir / 'src' / 'lib' / 'components'
        for (schema_name, table_name, stem, rname, iname,
             out_names, pk_info, pk_field, all_fields,
             has_post, has_put, has_del,
             post_in_names, put_in_names, map_key, crud_access, fk_deps, rev_fk_deps,
             optional_post_fields) in resources:
            self._write(
                components_dir / f'{stem}_list.svelte',
                _list_component(schema_name, table_name, stem, rname, iname,
                                out_names, pk_info, has_post, has_del, map_key, fk_deps),
            )

        # --- per-resource routes ---
        for (schema_name, table_name, stem, rname, iname,
             out_names, pk_info, pk_field, all_fields,
             has_post, has_put, has_del,
             post_in_names, put_in_names, map_key, crud_access, fk_deps, rev_fk_deps,
             optional_post_fields) in resources:

            res_dir = routes_dir / schema_name / table_name

            # list page — thin wrapper around the reusable component
            self._write(res_dir / '+page.svelte', _list_page(stem))

            # new (POST)
            if has_post:
                self._write(
                    res_dir / 'new' / '+page.svelte',
                    _new_page(schema_name, table_name, stem, rname, iname,
                              post_in_names, all_fields, optional_post_fields),
                )

            # detail (GET by pk)
            if pk_info and 'GET' in crud_access:
                self._write(
                    res_dir / '[id]' / '+page.svelte',
                    _detail_page(schema_name, table_name, stem, rname, iname,
                                 out_names, put_in_names, pk_field, all_fields,
                                 has_put, fk_deps, rev_fk_deps),
                )

        print(f'\nSvelteKit app generated in {output_dir}')
        print('Next steps:')
        print(f'  cd {output_dir}')
        print('  npm install')
        print('  npm run dev')

    def _write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        print(f'  {path}')
