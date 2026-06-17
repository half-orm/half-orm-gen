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
    "dev": "vite dev",
    "build": "vite build",
    "preview": "vite preview",
    "check": "svelte-kit sync && svelte-check --tsconfig ./tsconfig.json",
    "check:watch": "svelte-kit sync && svelte-check --tsconfig ./tsconfig.json --watch"
  }},
  "devDependencies": {{
    "@sveltejs/adapter-auto": "^3.0.0",
    "@sveltejs/kit": "^2.0.0",
    "@sveltejs/vite-plugin-svelte": "^5.0.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0",
    "svelte": "^5.0.0",
    "svelte-check": "^4.0.0",
    "tailwindcss": "^3.4.0",
    "typescript": "^5.0.0",
    "vite": "^6.0.0"
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
      '{version_prefix}': 'http://localhost:8000',
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
class AuthState {{
    token  = $state<string | null>(
        typeof sessionStorage !== 'undefined' ? sessionStorage.getItem('ho_token') : null
    );
    access = $state<Record<string, any>>({{}});

    login(t: string) {{
        sessionStorage.setItem('ho_token', t);
        this.token = t;
        this._fetchAccess();
    }}

    logout() {{
        sessionStorage.removeItem('ho_token');
        this.token = null;
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
}}

export const auth = new AuthState();

if (typeof window !== 'undefined') {{
    auth._fetchAccess();
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
    return ' '.join(p.capitalize() for p in (schema_name + '_' + table_name).split('_'))


def _layout(resources: list) -> str:
    nav_links = '\n      '.join(
        f'<a href="/{sn}/{tn}"'
        f' class="block px-3 py-2 rounded hover:bg-gray-100 text-sm text-gray-700">'
        f'{_title(sn, tn)}</a>'
        for sn, tn, *_ in resources
    )
    return f"""\
<script lang="ts">
  import '../app.css';
  import {{ auth }} from '$lib/auth.svelte.ts';

  let {{ children }} = $props();
</script>

<div class="min-h-screen flex bg-gray-50">
  <aside class="w-56 shrink-0 bg-white border-r flex flex-col">
    <div class="px-4 py-4 border-b">
      <span class="font-bold text-gray-800">API Browser</span>
    </div>
    <nav class="flex-1 overflow-y-auto px-2 py-3 space-y-0.5">
      {nav_links}
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
    out_names: list, pk_info,
    has_post: bool, has_del: bool,
    map_key: str,
    fk_deps: list,
) -> str:
    pk_field = pk_info[0] if pk_info else None
    title    = _title(schema_name, table_name)
    fk_map   = {local: (rs, rt) for local, rs, rt, _ in fk_deps}

    th_cols = '\n        '.join(
        f'<th class="px-4 py-2 text-left text-sm font-semibold text-gray-600">{f}</th>'
        for f in out_names
    )
    action_th = '<th class="px-4 py-2 w-20"></th>' if has_del and pk_field else ''

    def _td(f: str) -> str:
        if f in fk_map:
            rs, rt = fk_map[f]
            return (
                f'<td class="px-4 py-2 text-sm">'
                f'<a href="/{rs}/{rt}/{{item.{f}}}" onclick={{(e) => e.stopPropagation()}}'
                f' class="text-blue-500 hover:underline font-mono text-xs">{{item.{f}}}</a>'
                f'</td>'
            )
        return f'<td class="px-4 py-2 text-sm">{{item.{f} ?? ""}}</td>'

    td_cols = '\n          '.join(_td(f) for f in out_names)

    if pk_field:
        tr_open = (
            f'<tr class="border-t hover:bg-gray-50 cursor-pointer"'
            f' onclick={{() => goto(`/{schema_name}/{table_name}/${{item.{pk_field}}}`)}}'
            f'>'
        )
    else:
        tr_open = '<tr class="border-t hover:bg-gray-50">'

    action_td = ''
    if has_del and pk_field:
        action_td = (
            f'<td class="px-4 py-2 text-right">\n'
            f'          {{#if canDelete}}\n'
            f'            <button'
            f' onclick={{(e) => {{ e.stopPropagation(); handleDelete(item.{pk_field}); }}}}'
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
        f'      await {rname}Api.remove(id);\n'
        f'      items = items.filter(i => i.{pk_field} !== id);\n'
        f'    }}\n'
        f'  }}'
        if has_del and pk_field else ''
    )
    goto_import = "  import { goto } from '$app/navigation';\n" if pk_field else ''

    return f"""\
<script lang="ts">
  import {{ {rname}Api }} from '$lib/stores/{stem}.svelte.ts';
  import type {{ {iname}Out }} from '$lib/stores/{stem}.svelte.ts';
  import {{ auth }} from '$lib/auth.svelte.ts';
{goto_import}
  let {{ filters = {{}}, embedded = false }}: {{ filters?: Record<string, any>; embedded?: boolean }} = $props();

  let items = $state<{iname}Out[]>([]);

  $effect(() => {{
    {rname}Api.list(filters).then(r => r.json()).then(d => {{ items = d; }});
  }});
{can_create}{can_delete}{delete_fn}
</script>

{{#if !embedded}}
<div class="flex justify-between items-center mb-4">
  <h1 class="text-2xl font-bold">{title}</h1>{new_btn}
</div>
{{/if}}

<div class="bg-white shadow-sm rounded-lg overflow-hidden">
  <table class="w-full border-collapse">
    <thead class="bg-gray-100">
      <tr>
      {th_cols}
        {action_th}
      </tr>
    </thead>
    <tbody>
      {{#each items as item}}
        {tr_open}
        {td_cols}
          {action_td}
        </tr>
      {{/each}}
    </tbody>
  </table>
</div>
"""


def _list_page(stem: str) -> str:
    return f"""\
<script lang="ts">
  import List from '$lib/components/{stem}_list.svelte';
</script>

<List />
"""


def _new_page(
    schema_name: str, table_name: str,
    stem: str, rname: str, iname: str,
    post_in_names: list, all_fields: dict,
) -> str:
    title = _title(schema_name, table_name)
    fields_init = ', '.join(f'{f}: ""' for f in post_in_names)
    form_fields = '\n    '.join(
        f'<div>\n'
        f'      <label for="f_{f}" class="block text-sm font-medium text-gray-700 mb-1">{f}</label>\n'
        f'      <input id="f_{f}" bind:value={{form.{f}}}\n'
        f'             class="w-full border rounded px-3 py-2 text-sm" />\n'
        f'    </div>'
        for f in post_in_names
    )
    return f"""\
<script lang="ts">
  import {{ {rname}Api }} from '$lib/stores/{stem}.svelte.ts';
  import type {{ {iname}PostIn }} from '$lib/stores/{stem}.svelte.ts';
  import {{ goto }} from '$app/navigation';

  let form = $state<{iname}PostIn>({{ {fields_init} }});
  let error = $state('');

  async function handleSubmit(e: Event) {{
    e.preventDefault();
    try {{
      const res = await {rname}Api.create(form);
      if (!res.ok) throw new Error(await res.text());
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
        f'<div>\n'
        f'      <label for="f_{f}" class="block text-sm font-medium text-gray-700 mb-1">{f}</label>\n'
        f'      <input id="f_{f}" bind:value={{form.{f}}}\n'
        f'             class="w-full border rounded px-3 py-2 text-sm" />\n'
        f'    </div>'
        for f in put_in_names
    ) if put_in_names else ''

    # Form state + edit toggle — populated reactively from item once loaded
    extra_script = ''
    edit_btn     = ''
    edit_section = ''

    if has_put and put_in_names:
        empty_init  = ', '.join(f'{f}: ""' for f in put_in_names)
        effect_body = '\n        '.join(f'form.{f} = (item.{f} as string) ?? "";' for f in put_in_names)
        extra_script = (
            f'\n  let editing = $state(false);\n'
            f'  let form = $state({{ {empty_init} }});\n'
            f'  let error = $state(\'\');\n'
            f'  $effect(() => {{\n'
            f'    if (item) {{\n'
            f'        {effect_body}\n'
            f'    }}\n'
            f'  }});\n'
            f'\n  async function handleUpdate(e: Event) {{\n'
            f'    e.preventDefault();\n'
            f'    try {{\n'
            f'      const res = await {rname}Api.update(page.params.id, form);\n'
            f'      if (!res.ok) throw new Error(await res.text());\n'
            f'      editing = false;\n'
            f'      {rname}Api.get(page.params.id).then(r => r.json()).then(d => {{ item = d; }});\n'
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
        for _, rs, rt, _ in deps:
            s = f'{rs}_{rt}'
            cn, rn = _cname(rs, rt), _rname(rs, rt)
            lines.append(f"  import {{ {rn}Api }} from '$lib/stores/{s}.svelte.ts';")
            lines.append(f"  import type {{ {cn}Out }} from '$lib/stores/{s}.svelte.ts';")
        return ('\n' + '\n'.join(lines)) if lines else ''

    def _fk_ref_states(deps: list) -> str:
        lines = [
            f"  let {_rname(rs, rt)}Ref = $state<{_cname(rs, rt)}Out | null>(null);"
            for _, rs, rt, _ in deps
        ]
        return ('\n' + '\n'.join(lines)) if lines else ''

    def _fk_ref_effects(deps: list) -> str:
        blocks = []
        for lf, rs, rt, _ in deps:
            rn = _rname(rs, rt)
            blocks.append(
                f'  $effect(() => {{\n'
                f'    if (item?.{lf})\n'
                f'      {rn}Api.get(item.{lf}).then(r => r.json()).then(d => {{ {rn}Ref = d; }});\n'
                f'  }});'
            )
        return ('\n' + '\n'.join(blocks)) if blocks else ''

    def _fk_ref_section(lf: str, rs: str, rt: str, remote_pk: str) -> str:
        rn = _rname(rs, rt)
        return (
            f'\n{{#if {rn}Ref}}\n'
            f'<div class="max-w-2xl mx-auto mt-4 p-6 bg-white rounded-lg shadow">\n'
            f'  <div class="flex justify-between items-center mb-3">\n'
            f'    <h2 class="text-lg font-semibold">{_title(rs, rt)}</h2>\n'
            f'    <a href="/{rs}/{rt}/{{{rn}Ref.{remote_pk}}}"'
            f' class="text-sm text-blue-600 hover:underline">→</a>\n'
            f'  </div>\n'
            f'  <div class="space-y-1">\n'
            f'    {{#each Object.entries({rn}Ref) as [k, v]}}\n'
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
            f'\n<div class="max-w-2xl mx-auto mt-4 p-6 bg-white rounded-lg shadow">\n'
            f'  <h2 class="text-lg font-semibold mb-3">{_title(rs, rt)}</h2>\n'
            f'  {{#if item}}\n'
            f'    <{cn}List filters={{{{ {fk_field}: item.{pk_field} }}}} embedded />\n'
            f'  {{/if}}\n'
            f'</div>'
        )

    rev_sections = '\n'.join(_rev_section(rs, rt, fk) for rs, rt, fk in rev_fk_deps)

    return f"""\
<script lang="ts">
  import {{ {rname}Api }} from '$lib/stores/{stem}.svelte.ts';
  import type {{ {iname}Out{put_in_import} }} from '$lib/stores/{stem}.svelte.ts';
  import {{ goto }} from '$app/navigation';
  import {{ page }} from '$app/state';
  import {{ auth }} from '$lib/auth.svelte.ts';{fk_imports}{rev_imports}
{fk_states}
  let item = $state<{iname}Out | null>(null);

  $effect(() => {{
    {rname}Api.get(page.params.id).then(r => r.json()).then(d => {{ item = d; }});
  }});
{fk_effects}{can_edit}{extra_script}
</script>

{{#if item}}
<div class="max-w-2xl mx-auto p-6 bg-white rounded-lg shadow mt-6">
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
{fk_sections}
{rev_sections}
"""


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

class SvelteAppGenerator(StoreGenerator):

    def _fk_deps(self, inst, out_names: list, crud_resources: set) -> list:
        """Return (local_field, remote_schema, remote_table, remote_pk) for each
        simple non-reverse FK whose local field is in out_names and whose remote
        table has CRUD_ACCESS."""
        deps = []
        for fk in getattr(inst, '_ho_fkeys', {}).values():
            if fk.is_reverse:
                continue
            local_fields = fk.names
            remote_pks   = fk.fk_names
            if len(local_fields) != 1 or len(remote_pks) != 1:
                continue
            local_field = local_fields[0]
            if local_field not in out_names:
                continue
            fqtn = fk.remote['fqtn']
            remote_schema = fqtn[0].replace('.', '_')
            remote_table  = fqtn[1]
            if (remote_schema, remote_table) not in crud_resources:
                continue
            deps.append((local_field, remote_schema, remote_table, remote_pks[0]))
        return deps

    def _reverse_fk_deps(self, inst, pk_field: str | None, crud_resources: set) -> list:
        """Return (remote_schema, remote_table, fk_field) for each reverse FK
        whose remote table has CRUD_ACCESS. fk_field is the column in the remote
        table that references our PK."""
        if not pk_field:
            return []
        deps = []
        for fk in getattr(inst, '_ho_fkeys', {}).values():
            if not fk.is_reverse:
                continue
            our_pk_fields    = fk.names     # our PK columns being referenced
            remote_fk_fields = fk.fk_names  # FK columns in the remote table
            if len(our_pk_fields) != 1 or len(remote_fk_fields) != 1:
                continue
            if our_pk_fields[0] != pk_field:
                continue
            fqtn = fk.remote['fqtn']
            remote_schema = fqtn[0].replace('.', '_')
            remote_table  = fqtn[1]
            if (remote_schema, remote_table) not in crud_resources:
                continue
            deps.append((remote_schema, remote_table, remote_fk_fields[0]))
        return deps

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

        # --- auth store ---
        self._write(output_dir / 'src' / 'lib' / 'auth.svelte.ts', _auth_store(version_prefix))

        # Pass 1: identify all resources that expose CRUD_ACCESS
        crud_resources: set[tuple[str, str]] = set()
        raw = []
        for relation, _relation_type in classes:
            module_str = relation.__module__
            try:
                mod = importlib.import_module(module_str)
            except ImportError:
                continue
            if not getattr(mod, 'CRUD_ACCESS', None):
                continue
            schema_name = relation._schemaname.replace('.', '_')
            table_name  = relation.__name__.lower()
            crud_resources.add((schema_name, table_name))
            raw.append((relation, mod))

        # Pass 2: build per-resource metadata (needs complete crud_resources for fk_deps)
        resources = []
        for relation, mod in raw:
            crud_access  = mod.CRUD_ACCESS
            api_excluded = getattr(mod, 'API_EXCLUDED_FIELDS', [])
            schema_name  = relation._schemaname.replace('.', '_')
            table_name   = relation.__name__.lower()
            inst         = _instance(relation)
            all_fields   = getattr(inst, '_ho_fields', {})
            all_names    = list(all_fields.keys())
            pk_info      = _simple_pk(relation)
            pk_field     = pk_info[0] if pk_info else None
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

            post_in_names = _gen_in_fields(
                crud_access, 'POST', pk_field, api_excluded, all_names
            ) if has_post else []
            put_in_names = _gen_in_fields(
                crud_access, 'PUT', pk_field, api_excluded, all_names
            ) if has_put else []

            fk_deps     = self._fk_deps(inst, out_names, crud_resources)
            rev_fk_deps = self._reverse_fk_deps(inst, pk_field, crud_resources)

            resources.append((
                schema_name, table_name, stem, rname, iname,
                out_names, pk_info, pk_field, all_fields,
                has_post, has_put, has_del,
                post_in_names, put_in_names, map_key, crud_access, fk_deps, rev_fk_deps,
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
             post_in_names, put_in_names, map_key, crud_access, fk_deps, rev_fk_deps) in resources:
            self._write(
                components_dir / f'{stem}_list.svelte',
                _list_component(schema_name, table_name, stem, rname, iname,
                                out_names, pk_info, has_post, has_del, map_key, fk_deps),
            )

        # --- per-resource routes ---
        for (schema_name, table_name, stem, rname, iname,
             out_names, pk_info, pk_field, all_fields,
             has_post, has_put, has_del,
             post_in_names, put_in_names, map_key, crud_access, fk_deps, rev_fk_deps) in resources:

            res_dir = routes_dir / schema_name / table_name

            # list page — thin wrapper around the reusable component
            self._write(res_dir / '+page.svelte', _list_page(stem))

            # new (POST)
            if has_post:
                self._write(
                    res_dir / 'new' / '+page.svelte',
                    _new_page(schema_name, table_name, stem, rname, iname,
                              post_in_names, all_fields),
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
