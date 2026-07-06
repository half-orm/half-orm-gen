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

from half_orm_gen.backend.crud_routes import (
    _gen_out_fields,
    _gen_in_fields,
    _pk_info,
    _simple_pk,
    _instance,
    _py_type_str,
)
from half_orm_gen.frontend.base import (
    StoreGenerator,
    _title, _cname, _rname, _field_type_category,
    _is_bool_field, _is_text_field, _is_textarea_field,
    _is_required, _is_server_generated, _input_type, _text_fields,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
import {{ clearAllStates, clearStateForKey }} from '$lib/stateRegistry';

export type WsEvent = {{ event: 'create' | 'update' | 'delete' | 'access_reload'; resource: string; id: unknown }};
export type HoUser = {{ id: string; name: string; is_admin: boolean }};

class AuthState {{
    token         = $state<string | null>(
        typeof sessionStorage !== 'undefined' ? sessionStorage.getItem('ho_token') : null
    );
    access                = $state<Record<string, any>>({{}});
    roles                 = $state<string[]>([]);
    users                 = $state<HoUser[]>([]);
    hasAdmin              = $state<boolean | null>(null);
    lastEvent             = $state<WsEvent | null>(null);
    accessVersion         = $state(0);
    resourceAccessVersion = $state<Record<string, number>>({{}});
    fetchedRoutes         = new Set<string>();
    peers                 = $state<{{ name: string; url: string }}[]>([]);
    localAuthEnabled      = $state<boolean>(true);

    userId = $derived.by(() => {{
        const t = this.token;
        if (!t) return null;
        try {{ return (JSON.parse(atob(t.split('.')[1].replace(/-/g,'+').replace(/_/g,'/'))) as any)['sub'] ?? null; }}
        catch {{ return null; }}
    }});

    userRoles = $derived.by(() => {{
        const t = this.token;
        if (!t) return [] as string[];
        try {{ return (JSON.parse(atob(t.split('.')[1].replace(/-/g,'+').replace(/_/g,'/'))) as any)['roles'] ?? []; }}
        catch {{ return [] as string[]; }}
    }});

    displayName = $derived(
        this.userId
            ? (this.users.find(u => u.id === this.userId)?.name ?? 'anonymous')
            : 'anonymous'
    );

    isAdmin = $derived(
        !!this.userId && this.users.some(u => u.id === this.userId && u.is_admin)
    );

    setToken(jwt: string) {{
        sessionStorage.setItem('ho_token', jwt);
        this.token = jwt;
        this.fetchedRoutes = new Set();
        clearAllStates();
        void this._fetchAccess();
        void this._fetchRoles();
        void this._fetchUsers();
    }}

    logout() {{
        sessionStorage.removeItem('ho_token');
        this.token = null;
        this.fetchedRoutes = new Set();
        clearAllStates();
        if (typeof window !== 'undefined') goto('/');
        void this._fetchAccess();
        void this._fetchRoles();
    }}

    async loginWithEmail(email: string, password: string) {{
        const res = await fetch('{version_prefix}/auth/login', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{ email, password }}),
        }});
        if (!res.ok) throw new Error(((await res.json()) as any).detail ?? 'Login failed');
        this.setToken(((await res.json()) as any).token);
    }}

    async signupUser(name: string, email: string, password: string) {{
        const res = await fetch('{version_prefix}/auth/signup', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{ name, email, password }}),
        }});
        if (!res.ok) throw new Error(((await res.json()) as any).detail ?? 'Signup failed');
        this.setToken(((await res.json()) as any).token);
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

    async _fetchRoles() {{
        try {{
            const res = await fetch('{version_prefix}/ho_roles');
            if (res.ok) this.roles = await res.json();
        }} catch {{}}
    }}

    async _fetchUsers() {{
        try {{
            const res = await fetch('{version_prefix}/ho_users');
            if (res.ok) this.users = await res.json();
        }} catch {{}}
    }}

    async _fetchSetupStatus() {{
        try {{
            const res = await fetch('{version_prefix}/ho_setup');
            if (res.ok) this.hasAdmin = ((await res.json()) as any).has_admin;
        }} catch {{}}
    }}

    async _fetchPeers() {{
        try {{
            const res = await fetch('{version_prefix}/auth/peers');
            if (res.ok) {{
                const data = await res.json() as {{ peers: {{ name: string; url: string }}[]; local_auth_enabled: boolean }};
                this.peers = data.peers ?? [];
                this.localAuthEnabled = data.local_auth_enabled ?? true;
            }}
        }} catch {{}}
    }}

    loginUrlForPeer(name: string): string {{
        const returnTo = `${{window.location.origin}}/auth/callback`;
        return `{version_prefix}/auth/login?peer=${{encodeURIComponent(name)}}&return_to=${{encodeURIComponent(returnTo)}}`;
    }}

    async _reloadAccess(resource?: string) {{
        if (resource) {{
            for (const url of [...this.fetchedRoutes]) {{
                if (url.includes(`/${{resource}}`)) this.fetchedRoutes.delete(url);
            }}
            clearStateForKey(resource);
            await this._fetchAccess();
            this.resourceAccessVersion = {{
                ...this.resourceAccessVersion,
                [resource]: (this.resourceAccessVersion[resource] ?? 0) + 1,
            }};
        }} else {{
            this.fetchedRoutes = new Set();
            clearAllStates();
            await Promise.all([this._fetchAccess(), this._fetchRoles()]);
            this.accessVersion++;
        }}
    }}

    _connectWs() {{
        const base = (import.meta.env.VITE_WS_BASE ?? '').replace(/^http/, 'ws')
                     || `${{window.location.protocol === 'https:' ? 'wss' : 'ws'}}://${{window.location.host}}`;
        const ws = new WebSocket(`${{base}}{version_prefix}/ws`);
        ws.onmessage = (e) => {{
            try {{
                const msg = JSON.parse(e.data) as WsEvent;
                if (msg.event === 'access_reload') {{ void this._reloadAccess((msg as any).resource); }}
                this.lastEvent = msg;
            }} catch {{}}
        }};
        ws.onclose = () => {{ setTimeout(() => this._connectWs(), 2000); }};
        ws.onerror = () => ws.close();
    }}
}}

export const auth = new AuthState();

if (typeof window !== 'undefined') {{
    void auth._fetchAccess();
    void auth._fetchRoles();
    void auth._fetchUsers();
    void auth._fetchSetupStatus();
    void auth._fetchPeers();
    auth._connectWs();
}}
"""

def _login_page(version_prefix: str) -> str:
    return """\
<script lang="ts">
  import { auth } from '$lib/auth.svelte.ts';
</script>

<div class="flex flex-col items-center justify-center h-full text-gray-400 text-sm gap-2">
  {#if auth.token}
    <p>Signed in as <span class="font-semibold text-gray-700">{auth.displayName}</span></p>
    <p>Select a resource from the sidebar.</p>
  {:else}
    <p>Sign in using the button in the top right corner.</p>
  {/if}
</div>
"""

def _auth_callback_page() -> str:
    return """\
<script lang="ts">
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import { auth } from '$lib/auth.svelte.ts';

  let error = $state('');

  const token = page.url.searchParams.get('token');
  if (!token) {
    error = 'Missing token — sign-in did not complete.';
  } else {
    auth.setToken(token);
    goto('/', { replaceState: true });
  }
</script>

<div class="flex flex-col items-center justify-center h-full text-gray-400 text-sm gap-2">
  {#if error}
    <p class="text-red-500">{error}</p>
  {:else}
    <p>Signing you in…</p>
  {/if}
</div>
"""

def _auth_delegate_page(version_prefix: str) -> str:
    return f"""\
<script lang="ts">
  import {{ page }} from '$app/state';
  import {{ auth }} from '$lib/auth.svelte.ts';

  let email = $state('');
  let password = $state('');
  let error = $state('');
  let submitting = $state(false);
  let redirecting = $state(false);

  const redirectUri = page.url.searchParams.get('redirect_uri') ?? '';
  const csrfState = page.url.searchParams.get('csrf_state') ?? '';

  function redirectWithToken(token: string) {{
    redirecting = true;
    const sep = redirectUri.includes('?') ? '&' : '?';
    window.location.href = `${{redirectUri}}${{sep}}token=${{encodeURIComponent(token)}}&csrf_state=${{encodeURIComponent(csrfState)}}`;
  }}

  if (!redirectUri || !csrfState) {{
    error = 'Missing redirect_uri or csrf_state — this page must be reached via a peer login redirect.';
  }} else if (auth.token) {{
    // Already signed in on this peer, in this browser tab (sessionStorage) —
    // forward that existing token instead of asking for credentials again.
    // Same trust level as a fresh login: it's the same signed token either
    // way. Not a real cross-tab/cross-device SSO, just a same-tab shortcut —
    // see docs/internals/federation-protocol.md.
    redirectWithToken(auth.token);
  }}

  async function submit() {{
    if (!redirectUri || !csrfState || submitting) return;
    submitting = true;
    error = '';
    try {{
      const res = await fetch('{version_prefix}/auth/login', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ email, password }}),
      }});
      if (!res.ok) {{
        error = ((await res.json()) as any).detail ?? 'Login failed';
        return;
      }}
      const {{ token }} = (await res.json()) as {{ token: string }};
      redirectWithToken(token);
    }} finally {{
      submitting = false;
    }}
  }}
</script>

<div class="flex flex-col items-center justify-center h-full text-sm gap-3">
  {{#if error}}
    <p class="text-red-500">{{error}}</p>
  {{/if}}
  {{#if redirecting}}
    <p class="text-gray-400">Already signed in — redirecting…</p>
  {{:else}}
    <p class="text-gray-500">Sign in to continue to the requesting site.</p>
    <form onsubmit={{(e: Event) => {{ e.preventDefault(); void submit(); }}}} class="flex flex-col gap-2 w-64">
      <input bind:value={{email}} type="email" placeholder="Email" class="border rounded px-2 py-1 text-sm" />
      <input bind:value={{password}} type="password" placeholder="Password" class="border rounded px-2 py-1 text-sm" />
      <button type="submit" disabled={{submitting}}
              class="bg-blue-600 text-white rounded py-1 text-sm hover:bg-blue-700 disabled:opacity-50">
        {{submitting ? 'Signing in…' : 'Sign in'}}
      </button>
    </form>
  {{/if}}
</div>
"""


def _home_page() -> str:
    return """\
<div class="flex flex-col items-center justify-center h-screen bg-gray-50">
  <div class="relative group flex items-center gap-6 mb-6">
    <img src="/logo.png" alt="halfORM" class="h-30 w-auto" />
    <img src="/logo-chapeau.png" alt="" class="absolute inset-0 h-30 w-auto transition-opacity duration-[2000ms] opacity-100 group-hover:opacity-0" />
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

  const activeRole = $derived(auth.userRoles[0] ?? 'anonymous');

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
    {{#if auth.roles.length === 0}}
      <p class="text-gray-400 text-sm">Loading…</p>
    {{:else}}
      <div class="space-y-1">
        {{#each auth.roles as role}}
          <div class="w-full text-left px-3 py-2 rounded text-sm
                      {{auth.userRoles.includes(role) ? 'bg-blue-100 text-blue-700 font-semibold' : 'text-gray-700'}}">
            {{role}}
          </div>
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
        {{#each Object.entries(auth.access).sort(([a], [b]) => a.localeCompare(b)) as [resource, verbs]}}
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

def _schema_page_svelte() -> str:
    return """\
<script lang="ts">
  import { registry } from '$lib/generated/stores/silo-registry.svelte.ts';
  import type { FieldSchema, FkDep } from '$lib/generated/stores/schema.types';
  interface ResourceView {
    key: string;
    table: string;
    kind: string;
    fields: (FieldSchema & { fkTarget: string | null })[];
    reverseFks: string[];
  }

  let tocFilter = $state('');

  function scrollTo(id: string): void {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
  }

  const schemas = $derived.by(() => {
    const meta = registry.meta;
    const bySchema = new Map<string, ResourceView[]>();
    for (const [key, res] of Object.entries(meta)) {
      if (!bySchema.has(res.schema)) bySchema.set(res.schema, []);
      const fkByField = new Map<string, string>();
      for (const fk of res.fk_deps as FkDep[]) {
        for (const lf of fk.local_fields) fkByField.set(lf, `${fk.remote_schema}/${fk.remote_table}`);
      }
      bySchema.get(res.schema)!.push({
        key,
        table: res.table,
        kind: res.kind,
        fields: (res.fields as FieldSchema[]).map(f => ({ ...f, fkTarget: fkByField.get(f.name) ?? null })),
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

  const filteredSchemas = $derived.by(() => {
    const q = tocFilter.toLowerCase().trim();
    if (!q) return schemas;
    return schemas
      .map(s => ({
        ...s,
        resources: s.name.toLowerCase().includes(q)
          ? s.resources
          : s.resources.filter(r => r.table.toLowerCase().includes(q)),
      }))
      .filter(s => s.resources.length > 0);
  });
</script>

<aside class="w-max shrink-0 overflow-y-auto border-r bg-white flex flex-col">
  <div class="px-3 pt-3 pb-2 border-b">
    <input bind:value={tocFilter} placeholder="Filter…"
           class="w-full text-xs border rounded px-2 py-1 text-gray-700"/>
  </div>
  <div class="px-3 py-3 space-y-4 flex-1">
    {#each filteredSchemas as schema}
      <div>
        <button type="button" onclick={() => scrollTo('s__' + schema.name)}
           class="block text-xs font-semibold text-gray-500 uppercase tracking-wide hover:text-gray-800 cursor-pointer mb-1">
          {schema.name}
        </button>
        <ul class="space-y-0.5 pl-2">
          {#each schema.resources as res}
            <li>
              <button type="button" onclick={() => scrollTo(res.key.replace('/', '_'))}
                 class="text-sm text-blue-600 hover:underline cursor-pointer">{res.table}</button>
            </li>
          {/each}
        </ul>
      </div>
    {/each}
  </div>
</aside>

<div class="flex-1 overflow-y-auto px-6 py-6 space-y-10">
  <h1 class="text-2xl font-bold text-gray-800">Database Schema</h1>
  {#each schemas as schema}
    <section id={'s__' + schema.name}>
      <h2 class="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-3 border-b pb-1">
        {schema.name}
      </h2>
      <div class="space-y-4">
        {#each schema.resources as res}
          <div class="bg-white border rounded-lg overflow-hidden" id={res.key.replace('/', '_')}>
            <div class="flex items-center gap-2 px-4 py-2 bg-gray-50 border-b">
              <a href={'/ho_bo/' + res.key} class="font-semibold text-blue-700 hover:underline">{res.table}</a>
              <span class="text-xs text-gray-400 border rounded px-1">{res.kind}</span>
            </div>
            <table class="w-full text-sm">
              <tbody>
                {#each res.fields as field}
                  <tr class="border-b last:border-b-0 hover:bg-gray-50">
                    <td class="px-4 py-1.5 font-mono text-xs w-1/3"
                        class:font-bold={field.is_pk}
                        class:text-amber-700={field.is_pk}>
                      {field.is_pk ? '[PK] ' : ''}{field.name}
                    </td>
                    <td class="px-4 py-1.5 text-gray-500 text-xs w-1/4">{field.sql_type}</td>
                    <td class="px-4 py-1.5 text-xs">
                      {#if field.fkTarget}
                        <button type="button" onclick={() => scrollTo(field.fkTarget!.replace('/', '_'))}
                           class="text-blue-600 hover:underline cursor-pointer">&rightarrow; {field.fkTarget}</button>
                      {/if}
                    </td>
                  </tr>
                {/each}
                {#if res.reverseFks.length > 0}
                  <tr class="bg-gray-50 border-b">
                    <td colspan="3" class="px-4 py-1 text-xs font-semibold text-gray-400 uppercase tracking-wide">
                      Referenced by
                    </td>
                  </tr>
                  {#each res.reverseFks as rfk}
                    <tr class="border-b last:border-b-0 hover:bg-gray-50">
                      <td colspan="2"></td>
                      <td class="px-4 py-1.5 text-xs">
                        <button type="button" onclick={() => scrollTo(rfk.replace('/', '_'))}
                           class="text-indigo-500 hover:underline cursor-pointer">&leftarrow; {rfk}</button>
                      </td>
                    </tr>
                  {/each}
                {/if}
              </tbody>
            </table>
          </div>
        {/each}
      </div>
    </section>
  {/each}
</div>
"""


def _layout(resources: list, version_prefix: str = '') -> str:
    nav_items_js = ',\n    '.join(
        f'{{ href: "/ho_bo/{sn}/{tn}", label: "{_title(sn, tn)}" }}'
        for sn, tn, *_ in resources
    )
    return f"""\
<script lang="ts">
  import '../../app.css';
  import {{ auth }} from '$lib/auth.svelte.ts';
  import {{ registry }} from '$lib/generated/stores/silo-registry.svelte.ts';
  import {{ formatLabel }} from '$lib/generated/stores/silo-shared';
  import {{ page }} from '$app/state';
  import {{ goto }} from '$app/navigation';

  let {{ children }} = $props();
  let navFilter  = $state('');
  let menuOpen   = $state(!auth.token);
  let newItemsMenuOpen = $state(false);
  let showSignup = $state(false);
  let loginEmail = $state('');
  let loginPassword = $state('');
  let signupName = $state('');
  let signupEmail = $state('');
  let signupPassword = $state('');
  let authError  = $state('');

  let searchTerm     = $state('');
  let searchResource = $state('all');
  let searchOpen     = $state(false);
  let searchLoading  = $state(false);
  let searchResults  = $state<Record<string, any>>({{}});
  let searchDebounce: ReturnType<typeof setTimeout> | null = null;

  function logout() {{
    auth.logout();
    menuOpen = true;
    showSignup = false;
    loginEmail = ''; loginPassword = '';
    authError = '';
  }}

  async function doLogin() {{
    try {{
      authError = '';
      await auth.loginWithEmail(loginEmail, loginPassword);
      menuOpen = false;
      loginEmail = ''; loginPassword = '';
    }} catch (e: any) {{ authError = e.message; }}
  }}

  async function doSignup() {{
    try {{
      authError = '';
      await auth.signupUser(signupName, signupEmail, signupPassword);
      menuOpen = false;
      signupName = ''; signupEmail = ''; signupPassword = '';
    }} catch (e: any) {{ authError = e.message; }}
  }}

  function onSearchInput(val: string) {{
    searchTerm = val;
    if (searchDebounce) clearTimeout(searchDebounce);
    if (!val.trim()) {{ searchOpen = false; searchResults = {{}}; return; }}
    searchDebounce = setTimeout(() => runSearch(), 300);
  }}

  async function runSearch() {{
    const term = searchTerm.trim();
    if (!term) return;
    const res = searchResource;
    searchLoading = true;
    searchOpen = true;
    const headers: Record<string, string> = {{}};
    if (auth.token) headers['Authorization'] = `Bearer ${{auth.token}}`;
    try {{
      if (res === 'all') {{
        const r = await fetch(`{version_prefix}/ho_search?q=${{encodeURIComponent(term)}}&limit=5`, {{ headers }});
        searchResults = r.ok ? await r.json() : {{}};
      }} else {{
        const srch: string[] = (auth.access as any)[res]?.GET?.searchable ?? [];
        if (!srch.length) {{ searchResults = {{}}; return; }}
        const q = srch.map((f: string) => `${{f}}:${{term}}`).join(',');
        const r = await fetch(`{version_prefix}/${{res}}?q=${{encodeURIComponent(q)}}&limit=5`, {{ headers }});
        if (r.ok) {{
          const json = await r.json();
          searchResults = {{ [res]: {{ data: json.data ?? [], searchable_fields: srch, has_more: json.meta?.has_more ?? false }} }};
        }} else {{
          searchResults = {{}};
        }}
      }}
    }} finally {{
      searchLoading = false;
    }}
  }}

  function goToDetail(resource: string, row: Record<string, any>) {{
    const meta = (registry.meta as any)[resource];
    if (!meta) return;
    const pk: string[] = meta.pk_fields ?? [];
    const id = pk.length === 1
      ? String(row[pk[0]])
      : pk.map((f: string) => `${{f}}:${{row[f]}}`).join('::');
    goto(`/ho_bo/${{resource}}/${{id}}`);
    searchOpen = false;
  }}

  function formatResult(row: Record<string, any>, resource: string, fields: string[]): string {{
    const labelFields = ((registry.meta as any)[resource]?.label_fields ?? []) as string[];
    return formatLabel(row, labelFields, fields);
  }}

  function buildSeeAllHref(resource: string, term: string): string {{
    if (!term.trim()) return `/ho_bo/${{resource}}`;
    return `/ho_bo/search?q=${{encodeURIComponent(term.trim())}}&r=${{encodeURIComponent(resource)}}`;
  }}

  const navItems = [
    {nav_items_js}
  ].sort((a, b) => a.label.localeCompare(b.label));
  const filteredNav = $derived(
    navFilter
      ? navItems.filter(i => i.label.toLowerCase().includes(navFilter.toLowerCase()))
      : navItems
  );

  const searchableResources = $derived(
    Object.keys(auth.access as Record<string, any>)
      .filter(key => {{
        const srch = (auth.access as any)[key]?.GET?.searchable;
        return Array.isArray(srch) && srch.length > 0;
      }})
      .map(key => ({{ key, label: key.replace('/', '.') }}))
      .sort((a: any, b: any) => a.label.localeCompare(b.label))
  );
  const hasGlobalSearch = $derived(searchableResources.length > 0);

  const newItemsEntries = $derived(
    Object.entries(registry.newItemsByResource)
      .map(([resource, count]) => ({{ resource, label: resource.replace('/', '.'), count: count as number }}))
      .sort((a, b) => b.count - a.count)
  );
  const totalNewCount = $derived(newItemsEntries.reduce((sum, e) => sum + e.count, 0));
  const searchResultEntries = $derived(
    Object.entries(searchResults)
      .map(([resource, val]: [string, any]) => ({{
        resource,
        data: (val.data ?? []) as Record<string, any>[],
        searchable_fields: (val.searchable_fields ?? []) as string[],
        has_more: val.has_more ?? false,
        seeAllHref: buildSeeAllHref(resource, searchTerm),
      }}))
      .filter((e: any) => e.data.length > 0)
  );
</script>

<!-- svelte-ignore a11y_no_static_element_interactions a11y_click_events_have_key_events -->
<div class="h-screen flex flex-col bg-gray-50 overflow-hidden"
     onclick={{(e) => {{
       if (menuOpen && !(e.target as HTMLElement).closest('.auth-menu')) menuOpen = false;
       if (newItemsMenuOpen && !(e.target as HTMLElement).closest('.new-items-menu')) newItemsMenuOpen = false;
       if (searchOpen && !(e.target as HTMLElement).closest('.search-bar')) searchOpen = false;
     }}}}
     onkeydown={{(e) => {{ if (e.key === 'Escape') {{ menuOpen = false; newItemsMenuOpen = false; searchOpen = false; }} }}}}
     role="presentation">
  <header class="shrink-0 bg-white border-b h-11 flex items-center justify-between px-4">
    <span class="font-bold text-gray-800 shrink-0">halfORM Backoffice</span>
    {{#if hasGlobalSearch}}
      <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
      <div class="relative flex-1 mx-6 max-w-lg search-bar"
           onclick={{(e) => e.stopPropagation()}}
           onkeydown={{(e) => {{ if (e.key === 'Escape') searchOpen = false; }}}}>
        <div class="flex items-center border rounded text-xs bg-white overflow-hidden focus-within:ring-1 focus-within:ring-blue-300">
          <input value={{searchTerm}} oninput={{(e) => onSearchInput((e.target as HTMLInputElement).value)}}
                 onfocus={{() => {{ if (Object.keys(searchResults).length > 0) searchOpen = true; }}}}
                 placeholder="Search…"
                 class="flex-1 px-3 py-1.5 outline-none min-w-0"/>
          <select value={{searchResource}} onchange={{(e) => {{ searchResource = (e.target as HTMLSelectElement).value; }}}}
                  class="border-l px-2 py-1.5 bg-gray-50 text-gray-600 text-[11px] outline-none cursor-pointer max-w-[130px]">
            {{#if searchableResources.length > 1}}
              <option value="all">All</option>
            {{/if}}
            {{#each searchableResources as r}}
              <option value={{r.key}}>{{r.label}}</option>
            {{/each}}
          </select>
        </div>
        {{#if searchOpen}}
          <div class="absolute top-full left-0 right-0 mt-1 bg-white border rounded-lg shadow-xl z-50 max-h-96 overflow-y-auto">
            {{#if searchLoading}}
              <div class="px-4 py-3 text-xs text-gray-400">Searching…</div>
            {{:else if searchResultEntries.length === 0}}
              <div class="px-4 py-3 text-xs text-gray-400">No results</div>
            {{:else}}
              {{#each searchResultEntries as entry}}
                <div class="px-3 pt-2 pb-1 border-b last:border-b-0">
                  <span class="text-[10px] font-bold uppercase tracking-wide text-gray-400 mb-1 block">{{entry.resource.replace('/', '.')}}</span>
                  {{#each entry.data as row}}
                    <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
                    <div onclick={{() => goToDetail(entry.resource, row)}}
                         class="px-2 py-1.5 rounded hover:bg-blue-50 cursor-pointer text-xs text-gray-700 truncate">
                      {{formatResult(row, entry.resource, entry.searchable_fields)}}
                    </div>
                  {{/each}}
                  {{#if entry.has_more}}
                    <a href={{entry.seeAllHref}} onclick={{() => {{ searchOpen = false; }}}}
                       class="block text-[10px] text-blue-500 hover:underline mt-1">more…</a>
                  {{/if}}
                </div>
              {{/each}}
            {{/if}}
          </div>
        {{/if}}
      </div>
    {{/if}}
    <div class="flex items-center gap-2 shrink-0">
    <div class="relative auth-menu shrink-0">
      <button onclick={{(e) => {{ e.stopPropagation(); menuOpen = !menuOpen; }}}}
              class="flex items-center gap-1 text-xs px-3 py-1 rounded-full border
                     {{auth.token ? 'border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100' : 'border-gray-300 text-gray-500 hover:bg-gray-50'}}
                     transition-colors">
        {{auth.displayName}}
        <span class="opacity-60">{{menuOpen ? '▲' : '▼'}}</span>
      </button>
      {{#if menuOpen}}
        <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
        <div class="absolute right-0 top-full mt-1 bg-white border rounded-lg shadow-lg z-50 w-64 p-3"
             onclick={{(e) => e.stopPropagation()}}>
          {{#if auth.token}}
            <p class="text-xs text-gray-500 mb-2">Signed in as <strong>{{auth.displayName}}</strong></p>
            <button onclick={{logout}}
                    class="w-full text-left px-2 py-1.5 text-xs text-red-500 hover:bg-red-50 rounded transition-colors">
              Sign out
            </button>
          {{:else if auth.hasAdmin === false}}
            <p class="text-xs font-semibold text-gray-700 mb-3">Create admin account</p>
            <input bind:value={{signupName}} placeholder="Name"
                   class="w-full text-xs border rounded px-2 py-1.5 mb-2 focus:outline-none focus:ring-1 focus:ring-blue-400"/>
            <input bind:value={{signupEmail}} placeholder="Email" type="email"
                   class="w-full text-xs border rounded px-2 py-1.5 mb-2 focus:outline-none focus:ring-1 focus:ring-blue-400"/>
            <input bind:value={{signupPassword}} placeholder="Password" type="password"
                   class="w-full text-xs border rounded px-2 py-1.5 mb-2 focus:outline-none focus:ring-1 focus:ring-blue-400"/>
            {{#if authError}}<p class="text-xs text-red-500 mb-1">{{authError}}</p>{{/if}}
            <button onclick={{doSignup}}
                    class="w-full text-xs bg-blue-600 text-white px-2 py-1.5 rounded hover:bg-blue-700 transition-colors">
              Create account
            </button>
          {{:else}}
            {{#if auth.peers.length > 0}}
              <p class="text-xs font-semibold text-gray-700 mb-2">Sign in via</p>
              <div class="space-y-1 mb-3">
                {{#each auth.peers as p}}
                  <a href={{auth.loginUrlForPeer(p.name)}}
                     class="block w-full text-xs text-center border rounded px-2 py-1.5 text-gray-700 hover:bg-gray-50 transition-colors">
                    {{p.name}}
                  </a>
                {{/each}}
              </div>
            {{/if}}
            {{#if auth.localAuthEnabled}}
              {{#if !showSignup}}
                <p class="text-xs font-semibold text-gray-700 mb-3">Sign in</p>
                <input bind:value={{loginEmail}} placeholder="Email" type="email"
                       class="w-full text-xs border rounded px-2 py-1.5 mb-2 focus:outline-none focus:ring-1 focus:ring-blue-400"/>
                <input bind:value={{loginPassword}} placeholder="Password" type="password"
                       onkeydown={{(e) => {{ if (e.key === 'Enter') doLogin(); }}}}
                       class="w-full text-xs border rounded px-2 py-1.5 mb-2 focus:outline-none focus:ring-1 focus:ring-blue-400"/>
                {{#if authError}}<p class="text-xs text-red-500 mb-1">{{authError}}</p>{{/if}}
                <button onclick={{doLogin}}
                        class="w-full text-xs bg-blue-600 text-white px-2 py-1.5 rounded hover:bg-blue-700 transition-colors mb-2">
                  Sign in
                </button>
                <button onclick={{() => {{ showSignup = true; authError = ''; }}}}
                        class="w-full text-xs text-blue-500 hover:underline">
                  Create account
                </button>
              {{:else}}
                <p class="text-xs font-semibold text-gray-700 mb-3">Create account</p>
                <input bind:value={{signupName}} placeholder="Name"
                       class="w-full text-xs border rounded px-2 py-1.5 mb-2 focus:outline-none focus:ring-1 focus:ring-blue-400"/>
                <input bind:value={{signupEmail}} placeholder="Email" type="email"
                       class="w-full text-xs border rounded px-2 py-1.5 mb-2 focus:outline-none focus:ring-1 focus:ring-blue-400"/>
                <input bind:value={{signupPassword}} placeholder="Password" type="password"
                       class="w-full text-xs border rounded px-2 py-1.5 mb-2 focus:outline-none focus:ring-1 focus:ring-blue-400"/>
                {{#if authError}}<p class="text-xs text-red-500 mb-1">{{authError}}</p>{{/if}}
                <button onclick={{doSignup}}
                        class="w-full text-xs bg-blue-600 text-white px-2 py-1.5 rounded hover:bg-blue-700 transition-colors mb-2">
                  Create account
                </button>
                <button onclick={{() => {{ showSignup = false; authError = ''; }}}}
                        class="w-full text-xs text-gray-400 hover:underline">
                  Back to sign in
                </button>
              {{/if}}
            {{/if}}
          {{/if}}
        </div>
      {{/if}}
    </div>
    {{#if totalNewCount > 0}}
      <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
      <div class="relative new-items-menu shrink-0" onclick={{(e) => e.stopPropagation()}}>
        <button onclick={{() => newItemsMenuOpen = !newItemsMenuOpen}}
                class="flex items-center gap-1 text-xs px-3 py-1 rounded bg-blue-600 text-white hover:bg-blue-700 transition-colors">
          🔔 {{totalNewCount}}
        </button>
        {{#if newItemsMenuOpen}}
          <div class="absolute right-0 top-full mt-1 bg-white border rounded-lg shadow-lg z-50 w-64 p-2">
            {{#each newItemsEntries as entry}}
              <a href={{`/ho_bo/${{entry.resource}}?new=1`}}
                 onclick={{() => newItemsMenuOpen = false}}
                 class="flex justify-between items-center px-2 py-1.5 rounded hover:bg-blue-50 text-sm text-gray-700">
                <span>{{entry.label}}</span>
                <span class="text-xs bg-blue-600 text-white rounded-full px-1.5 py-0.5">{{entry.count}}</span>
              </a>
            {{/each}}
          </div>
        {{/if}}
      </div>
    {{/if}}
    </div>
  </header>
  <div class="flex flex-1 overflow-hidden">
    <aside class="w-max shrink-0 bg-white border-r flex flex-col">
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
      <div class="px-4 py-3 border-t flex items-center justify-between">
        <a href="/schema" title="Schema"
           class="transition-colors {{page.url.pathname === '/schema' ? 'text-blue-600' : 'text-gray-400 hover:text-blue-600'}}">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="w-6 h-6">
            <path d="M21 6.375c0 2.692-4.03 4.875-9 4.875S3 9.067 3 6.375 7.03 1.5 12 1.5s9 2.183 9 4.875z" />
            <path d="M12 12.75c2.685 0 5.19-.586 7.078-1.609a8.283 8.283 0 001.897-1.384c.016.121.025.244.025.368C21 12.817 16.97 15 12 15s-9-2.183-9-4.875c0-.124.009-.247.025-.368a8.285 8.285 0 001.897 1.384C6.809 12.164 9.315 12.75 12 12.75z" />
            <path d="M12 16.5c2.685 0 5.19-.586 7.078-1.609a8.282 8.282 0 001.897-1.384c.016.121.025.244.025.368 0 2.692-4.03 4.875-9 4.875s-9-2.183-9-4.875c0-.124.009-.247.025-.368a8.284 8.284 0 001.897 1.384C6.809 15.914 9.315 16.5 12 16.5z" />
          </svg>
        </a>
      </div>
    </aside>
    <main class={{page.url.pathname === '/schema' ? 'flex-1 overflow-hidden flex' : 'flex-1 overflow-y-auto p-6'}}>
      {{@render children()}}
    </main>
  </div>
</div>
"""


def _search_page_svelte(version_prefix: str) -> str:
    return f"""\
<script lang="ts">
  import {{ goto }} from '$app/navigation';
  import {{ page }} from '$app/stores';
  import {{ auth }} from '$lib/auth.svelte.ts';
  import {{ registry }} from '$lib/generated/stores/silo-registry.svelte.ts';
  import {{ formatLabel }} from '$lib/generated/stores/silo-shared';

  const API_BASE = '{version_prefix}';

  let results  = $state<Record<string, any>>({{  }});
  let loading  = $state(false);
  let searched = $state(false);

  const q = $derived($page.url.searchParams.get('q') ?? '');
  const r = $derived($page.url.searchParams.get('r') ?? 'all');

  $effect(() => {{
    void q; void r;
    if (!q.trim()) {{ results = {{  }}; searched = false; return; }}
    void runSearch(q, r);
  }});

  async function runSearch(term: string, resource: string): Promise<void> {{
    loading = true;
    const headers: Record<string, string> = {{}};
    const tok = auth.token;
    if (tok) headers['Authorization'] = `Bearer ${{tok}}`;
    try {{
      const resParam = resource && resource !== 'all' ? `&resource=${{encodeURIComponent(resource)}}` : '';
      const res = await fetch(`${{API_BASE}}/ho_search?q=${{encodeURIComponent(term)}}&limit=50${{resParam}}`, {{ headers }});
      results = res.ok ? await res.json() : {{  }};
    }} finally {{
      loading = false;
      searched = true;
    }}
  }}

  const resultEntries = $derived(
    Object.entries(results)
      .map(([resource, val]: [string, any]) => ({{
        resource,
        data: (val.data ?? []) as Record<string, any>[],
        searchable_fields: (val.searchable_fields ?? []) as string[],
      }}))
      .filter((e: any) => e.data.length > 0)
  );

  function goToDetail(resource: string, row: Record<string, any>): void {{
    const meta = (registry.meta as any)[resource];
    if (!meta) return;
    const pk: string[] = meta.pk_fields ?? [];
    const id = pk.length === 1
      ? String(row[pk[0]])
      : pk.map((f: string) => `${{f}}:${{row[f]}}`).join('::');
    goto(`/ho_bo/${{resource}}/${{id}}`);
  }}

  function formatResult(row: Record<string, any>, resource: string, fields: string[]): string {{
    const labelFields = ((registry.meta as any)[resource]?.label_fields ?? []) as string[];
    return formatLabel(row, labelFields, fields);
  }}
</script>

<div class="px-4 py-6 max-w-3xl mx-auto">
  <h1 class="text-xl font-bold mb-1">Search results</h1>
  {{#if q}}
    <p class="text-sm text-gray-500 mb-4">
      for "<span class="font-medium text-gray-700">{{q}}</span>"
      {{#if r !== 'all'}}
        in <span class="font-medium text-gray-700">{{r.replace('/', '.')}}</span>
      {{/if}}
    </p>
  {{/if}}
  {{#if loading}}
    <div class="text-gray-400 text-sm py-8 text-center">Searching…</div>
  {{:else if searched && resultEntries.length === 0}}
    <div class="text-gray-400 text-sm py-8 text-center">No results found.</div>
  {{:else}}
    {{#each resultEntries as entry}}
      <div class="mb-6">
        <h2 class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
          <a href="/ho_bo/{{entry.resource}}" class="hover:underline hover:text-blue-700">
            {{entry.resource.replace('/', '.')}}
          </a>
        </h2>
        <div class="bg-white rounded-lg shadow overflow-hidden divide-y">
          {{#each entry.data as row}}
            <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
            <div onclick={{() => goToDetail(entry.resource, row)}}
                 class="px-4 py-3 hover:bg-blue-50 cursor-pointer text-sm text-gray-700">
              {{formatResult(row, entry.resource, entry.searchable_fields)}}
            </div>
          {{/each}}
        </div>
      </div>
    {{/each}}
  {{/if}}
</div>
"""


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
            f"() => {{ if (silo.sortField === '{f}') silo.sortAsc = !silo.sortAsc;"
            f" else {{ silo.sortField = '{f}'; silo.sortAsc = true; }} }}"
        )
        indicator = f"{{#if silo.sortField === '{f}'}}{{silo.sortAsc ? '↑' : '↓'}}{{/if}}"
        return (
            f'{{#if !silo.inaccessibleFields().has(\'{f}\')}}'
            f'<th onclick={{{toggle}}}'
            f' class="px-4 py-2 text-left text-sm font-semibold text-gray-600 cursor-pointer select-none hover:bg-gray-200">'
            f'{f} {indicator}</th>'
            f'{{/if}}'
        )

    action_th = '<th class="px-2 py-2 w-16"></th>' if pk_field else ''
    th_cols   = (action_th + '\n        ' if action_th else '') + '\n        '.join(_sort_th(f) for f in out_names)

    _filter_help_html = ''.join(
        f'<li class="flex gap-1.5"><code class="shrink-0 rounded bg-gray-100 px-1 py-0.5 text-[10px] text-gray-800">{code}</code>'
        f'<span>{desc}</span></li>'
        for code, desc in [
            ('text', 'starts with'),
            ('*text', 'anywhere in the field'),
            ('&gt; &lt; &gt;= &lt;=', 'numeric/date comparison'),
            ('&gt;=A&lt;=B', 'range'),
        ]
    )
    filter_inputs = '\n        '.join(
        f'{{#if !silo.inaccessibleFields().has(\'{f}\') && silo.searchableFields.includes(\'{f}\')}}'
        f'<th class="px-2 py-1">'
        f'<div class="relative">'
        f'<input value={{localFilters[\'{f}\'] ?? \'\'}} '
        f'oninput={{(e) => localFilters = {{...localFilters, \'{f}\': e.currentTarget.value}}}} '
        f'placeholder="…" class="w-full text-xs border rounded pl-2 pr-5 py-1 font-normal" />'
        f'<div class="absolute right-1.5 top-1/2 -translate-y-1/2 flex items-center">'
        f'<Tooltip align="right">'
        f'{{#snippet trigger()}}<span class="flex h-3.5 w-3.5 items-center justify-center rounded-full bg-gray-200 text-[9px] font-semibold text-gray-500 cursor-help select-none leading-none">?</span>{{/snippet}}'
        f'<ul class="space-y-1">{_filter_help_html}</ul>'
        f'</Tooltip>'
        f'</div>'
        f'</div>'
        f'</th>'
        f'{{:else if !silo.inaccessibleFields().has(\'{f}\')}}'
        f'<th class="px-2 py-1"></th>'
        f'{{/if}}'
        for f in out_names
    )
    action_filter_th = (
        '<th class="px-2 py-1 whitespace-nowrap">'
        '<Tooltip>'
        '{#snippet trigger()}<button onclick={() => clearAllFilters()} '
        'disabled={Object.keys(localFilters).length === 0} '
        'class="text-xs text-blue-600 hover:text-blue-800 disabled:text-gray-400 disabled:cursor-not-allowed">✕</button>{/snippet}'
        'Clear all filters'
        '</Tooltip>'
        '</th>'
    ) if pk_field else ''
    filter_row = (
        f'\n      {{#if !embedded}}\n'
        f'      <tr class="bg-white border-b">\n'
        f'        {action_filter_th}\n'
        f'        {filter_inputs}\n'
        f'      </tr>\n'
        f'      {{/if}}'
    )

    def _td(f: str) -> str:
        inacc = f"silo.inaccessibleFields().has('{f}')"
        if f in fk_map:
            rs, rt = fk_map[f]
            return (
                f'{{#if !{inacc}}}'
                f'<td class="px-4 py-2 text-sm">'
                f'<a href="/ho_bo/{rs}/{rt}/{{item.{f}}}"'
                f' onclick={{(e) => {{ e.preventDefault(); e.stopPropagation(); goto(`/ho_bo/{rs}/{rt}/${{item.{f}}}`); }}}}'
                f' class="text-blue-500 hover:underline font-mono text-xs truncate block" class:max-w-xs={{!embedded}}'
                f' title="{{cellTitle(item.{f})}}">{{fmtCell(item.{f})}}</a>'
                f'</td>'
                f'{{/if}}'
            )
        cell_click = (
            f"(e) => {{ const _j = (item as any).{f}; "
            f"if (_j != null && typeof _j === 'object') {{ e.stopPropagation(); showJson(_j); }} }}"
        )
        return (
            f'{{#if !{inacc}}}'
            f'<td class="px-4 py-2 text-sm" onclick={{{cell_click}}}>'
            f'<div class="truncate" class:max-w-xs={{!embedded}} title="{{cellTitle(item.{f})}}"'
            f' class:text-blue-600={{typeof (item as any).{f} === \'object\' && (item as any).{f} != null}}'
            f' class:cursor-pointer={{typeof (item as any).{f} === \'object\' && (item as any).{f} != null}}>'
            f'{{fmtCell(item.{f})}}</div>'
            f'</td>'
            f'{{/if}}'
        )

    td_cols = '\n          '.join(_td(f) for f in out_names)

    if pk_field:
        tr_attrs = (
            f'class="border-t hover:bg-gray-50 cursor-pointer" '
            f'class:bg-blue-50={{silo.selectedId === String({pk_item_expr})}} '
            f'class:border-l-4={{silo.selectedId === String({pk_item_expr})}} '
            f'class:border-l-blue-500={{silo.selectedId === String({pk_item_expr})}} '
            f'data-item-id={{String({pk_item_expr})}} '
            f'onclick={{() => selectAndNavigate(String({pk_item_expr}))}}'
        )
    else:
        tr_attrs = 'class="border-t hover:bg-gray-50"'

    action_td = ''
    if pk_field:
        action_td = (
            f'<td class="px-2 py-2">\n'
            f'          <div class="flex items-center gap-1.5">\n'
            f'          {{#if silo.isNew(String({pk_item_expr}))}}\n'
            f'            <span class="inline-block w-2 h-2 rounded-full bg-blue-500 shrink-0" title="New"></span>\n'
            f'          {{/if}}\n'
            f'          {{#if silo.canAccess(\'DELETE\', String({pk_item_expr}))}}\n'
            f'            <button'
            f' onclick={{(e) => {{ e.stopPropagation(); handleDelete({pk_item_expr}); }}}}'
            f'\n                    class="text-red-600 hover:underline text-sm">Delete</button>\n'
            f'          {{/if}}\n'
            f'          </div>\n'
            f'        </td>'
        )

    new_btn = (
        f'\n  {{#if silo.canCreateWithFilters(filters)}}\n'
        f'    <a href={{fkNewUrl()}}\n'
        f'       class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 text-sm">\n'
        f'      New\n    </a>\n  {{/if}}'
        if has_post else ''
    )

    new_items_badge = (
        '<NewItemsBadge count={contextualNewCount} active={showNewOnly} ontoggle={toggleShowNewOnly} />'
        if pk_field else ''
    )

    delete_fn  = (
        f'\n  async function handleDelete(id: string) {{\n'
        f'    if (confirm(\'Delete this item?\')) {{\n'
        f'      const res = await silo.remove(id);\n'
        f'      if (res.ok) silo.removeItem(String(id));\n'
        f'    }}\n'
        f'  }}'
        if pk_field else ''
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
  import Tooltip from '$lib/generated/Tooltip.svelte';
  import NewItemsBadge from '$lib/generated/NewItemsBadge.svelte';

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
  import {{ registry }} from '$lib/generated/stores/silo-registry.svelte.ts';
  import type {{ Row }} from '$lib/generated/stores/resource.silo.svelte.ts';
  import {{ auth }} from '$lib/auth.svelte.ts';
  import {{ goto }} from '$app/navigation';
  let {{ filters = {{}}, embedded = false }}: {{ filters?: Record<string, any>; embedded?: boolean }} = $props();

  const silo = registry.get('{map_key}');
  const hasFilters = $derived(Object.keys(filters).length > 0);
{field_types_code}
{"" if not pk_field else f"""
  let localFilters = $state<Record<string, string>>({{}});
  let showNewOnly = $state(false);
  function toggleShowNewOnly() {{ showNewOnly = !showNewOnly; }}

  // Initialize localFilters from URL or silo on mount (using a closure to run once)
  (() => {{
    if (embedded) return;
    const sp = new URLSearchParams(window.location.search);
    if (sp.get('new') === '1') showNewOnly = true;
    const urlFilters = initFiltersFromUrl(sp);
    if (Object.keys(urlFilters).length > 0) {{
      // URL has priority
      localFilters = urlFilters;
      silo.filters = urlFilters;
    }} else {{
      // Try to restore from silo
      const siloFilters = silo.filters;
      if (Object.keys(siloFilters).length > 0) {{
        localFilters = siloFilters;
        // Update URL to reflect silo filters
        const newUrl = buildUrlWithFilters(window.location.pathname, siloFilters);
        if (newUrl !== window.location.pathname + window.location.search) {{
          goto(newUrl, {{ replaceState: true, keepFocus: true }});
        }}
      }}
    }}
  }})();

  function clearAllFilters() {{
    localFilters = {{}};
  }}

  function selectAndNavigate(id: string) {{
    silo.selectedId = id;
    goto(`/ho_bo/{schema_name}/{table_name}/${{id}}`);
  }}

  const contextItems = $derived.by(() => {{
    let items: Row[] = hasFilters
      ? silo.items.filter(item =>
            Object.entries(filters).every(([k, v]) => String((item as any)[k]) === String(v)))
      : silo.items;
    const lf = localFilters;
    if (Object.values(lf).some(v => v))
      items = items.filter(item =>
        Object.entries(lf).every(([k, v]) => matchFilter((item as any)[k], v)));
    return items;
  }});

  // "New" count scoped to this list's own context (parent FK filter + local
  // filters) — not the silo's resource-wide count, which would leak e.g. a new
  // comment on a DIFFERENT post into this post's embedded comment list.
  const contextualNewCount = $derived(
    contextItems.filter(item => silo.isNew(String({pk_item_expr}))).length
  );

  const displayItems = $derived.by(() => {{
    let items: Row[] = contextItems;
    if (showNewOnly) {{
      items = items.filter(item => silo.isNew(String({pk_item_expr})));
    }}
    const sf = silo.sortField;
    if (sf) {{
      const asc = silo.sortAsc;
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
    let items: Row[] = silo.items;
    const lf = localFilters;
    if (Object.values(lf).some(v => v))
      items = items.filter(item =>
        Object.entries(lf).every(([k, v]) => matchFilter((item as any)[k], v)));
    const sf = silo.sortField;
    if (sf) {{
      const asc = silo.sortAsc;
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
    void auth.token;
    void auth.accessVersion;
    void (auth.resourceAccessVersion as any)[silo.key];
    void silo.list(filters);
  }});

  function loadMore() {{ silo.loadMore(filters); }}

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
        // Reset pagination state
        silo.resetFilterState();
        const searchParams = hasFiltersNow ? {{ q: filterPairs.join(',') }} as any : {{}};
        void silo.list(searchParams, 0);
      }}
    }}, 600);
  }});

  // Sync filters to URL and silo (with debounce handling)
  let urlSyncTimer: number | undefined;
  $effect(() => {{
    if (embedded) return; // Don't sync URL for embedded components

    // Track localFilters changes
    const lf = localFilters;

    if (urlSyncTimer) clearTimeout(urlSyncTimer);
    urlSyncTimer = window.setTimeout(() => {{
      // Update silo with current filters
      silo.filters = lf;

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
  // Silo handles WS updates; list reacts via $state signals automatically

  // Scroll to selected item when component mounts or items change
  $effect(() => {{
    const selectedId = silo.selectedId;
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
{delete_fn}
  let jsonDialog = $state<string | null>(null);
  function showJson(v: unknown): void {{ jsonDialog = JSON.stringify(v, null, 2); }}

  function fkNewUrl(): string {{
    const base = '/ho_bo/{schema_name}/{table_name}/new';
    const fkAuto = silo.fkAutoFields('POST');
    const params = new URLSearchParams();
    for (const [field, rule] of Object.entries(fkAuto)) {{
      if (rule === 'context' && filters[field] != null) params.set(field, String(filters[field]));
    }}
    const qs = params.toString();
    return qs ? `${{base}}?${{qs}}` : base;
  }}
</script>

{{#if !embedded}}
<div class="flex justify-between items-center mb-4">
  <h1 class="text-2xl font-bold">{title}</h1>
  <div class="flex items-center gap-3">{new_items_badge}{new_btn}</div>
</div>
{{:else}}{(new_btn or new_items_badge) and f'''
<div class="flex justify-end items-center gap-3 py-1 pr-1">{new_items_badge}{new_btn}
</div>''' or ''}
{{/if}}

<div class="{{embedded ? 'overflow-x-auto' : 'bg-white shadow-sm rounded-lg overflow-auto max-h-[calc(100vh-10rem)]'}}">
  <table class="w-full border-collapse">
    <thead class="{{embedded ? 'bg-gray-100' : 'bg-gray-100 sticky top-0 z-10 shadow-sm'}}">
      <tr>
      {th_cols}
      </tr>{filter_row}
    </thead>
    <tbody>
      {{#each displayItems as item, i}}
        <tr use:onIntersect={{i === displayItems.length - 1}} {tr_attrs}>
          {action_td}
        {td_cols}
        </tr>
      {{/each}}
      {{#if silo.isLoading}}
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
  let { children } = $props();
</script>

{@render children()}
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


def _null_map_js(text_fields_var: str = 'textFields') -> str:
    return f'.map(([k, v]) => [k, !{text_fields_var}.has(k) && v === \'\' ? null : v] as [string, unknown])'


def _svelte_form_field(f: str, all_fields: dict, bind_prefix: str = 'form', fk_target: tuple | None = None) -> str:
    req      = _is_required(f, all_fields)
    req_attr = ' required' if req else ''
    req_mark = ' <span class="text-red-500">*</span>' if req else ''
    itype    = _input_type(f, all_fields)
    if _is_bool_field(f, all_fields):
        default_field = (
            f'<div class="flex items-center gap-2">\n'
            f'      <input id="f_{f}" type="checkbox" bind:checked={{{bind_prefix}.{f}}}\n'
            f'             class="h-4 w-4 rounded border-gray-300" />\n'
            f'      <label for="f_{f}" class="text-sm font-medium text-gray-700">{f}</label>\n'
            f'    </div>'
        )
    elif _is_textarea_field(f, all_fields):
        default_field = (
            f'<div>\n'
            f'      <label for="f_{f}" class="block text-sm font-medium text-gray-700 mb-1">{f}{req_mark}</label>\n'
            f'      <textarea id="f_{f}" bind:value={{{bind_prefix}.{f}}}{req_attr}\n'
            f'               class="w-full border rounded px-3 py-2 text-sm font-mono resize-y min-h-[1rem] [field-sizing:content]"></textarea>\n'
            f'    </div>'
        )
    else:
        default_field = (
            f'<div>\n'
            f'      <label for="f_{f}" class="block text-sm font-medium text-gray-700 mb-1">{f}{req_mark}</label>\n'
            f'      <input id="f_{f}" type="{itype}" bind:value={{{bind_prefix}.{f}}}{req_attr}\n'
            f'             class="w-full border rounded px-3 py-2 text-sm" />\n'
            f'    </div>'
        )
    if fk_target is None:
        return default_field
    rs, rt = fk_target
    target_key = f'{rs}/{rt}'
    return (
        f"{{#if silo.fkAutoFields('POST')['{f}'] === 'select'}}\n"
        f'    <div class="relative">\n'
        f'      <label for="f_{f}" class="block text-sm font-medium text-gray-700 mb-1">{f}{req_mark}</label>\n'
        f'      <input type="hidden" bind:value={{{bind_prefix}.{f}}} name="{f}"{req_attr} />\n'
        f'      <input id="f_{f}" type="text" placeholder="Type to search…"\n'
        f"             value={{fkComboText['{f}'] ?? ''}}\n"
        f"             oninput={{(e: Event) => onFkComboInput('{f}', '{target_key}', (e.target as HTMLInputElement).value)}}\n"
        f"             onfocus={{() => openFkCombo('{f}')}} onblur={{() => closeFkCombo('{f}')}}\n"
        f'             class="w-full border rounded px-3 py-2 text-sm" />\n'
        f"      {{#if fkComboOpen['{f}']}}\n"
        f'      <div class="absolute z-10 mt-1 w-full bg-white border rounded-lg shadow-lg max-h-56 overflow-y-auto">\n'
        f"        {{#each fkOptions('{target_key}') as opt (opt.id)}}\n"
        f"          <div onmousedown={{() => selectFkOption('{f}', opt)}}\n"
        f'               class="px-3 py-1.5 text-sm hover:bg-blue-50 cursor-pointer">{{opt.label}}</div>\n'
        f'        {{:else}}\n'
        f'          <div class="px-3 py-1.5 text-sm text-gray-400">No match</div>\n'
        f'        {{/each}}\n'
        f'      </div>\n'
        f'      {{/if}}\n'
        f'    </div>\n'
        f'  {{:else}}\n'
        f'    {default_field}\n'
        f'  {{/if}}'
    )


def _new_page(
    schema_name: str, table_name: str,
    stem: str, rname: str, iname: str,
    post_in_names: list, all_fields: dict,
    optional_post_fields: frozenset = frozenset(),
    fk_deps: list = (),
) -> str:
    title = _title(schema_name, table_name)
    visible_post = [f for f in post_in_names if not _is_server_generated(f, all_fields)]
    fk_map = {lf: (rs, rt) for lf, rs, rt, _ in fk_deps}
    fields_init = ', '.join(
        f'{f}: false' if _is_bool_field(f, all_fields) else f'{f}: ""'
        for f in visible_post
    )
    map_key         = f'{schema_name}/{table_name}'
    optional_set_js = ', '.join(f"'{f}'" for f in optional_post_fields)
    text_fields_js  = _text_fields(visible_post, all_fields)
    form_fields = '\n    '.join(
        f"{{#if !silo.inaccessibleFields('POST').has('{f}')}}\n    "
        + _svelte_form_field(f, all_fields, fk_target=fk_map.get(f))
        + '\n    {/if}'
        for f in visible_post
    )
    fk_targets_js = ', '.join(
        f"'{f}': '{rs}/{rt}'" for f, (rs, rt) in fk_map.items() if f in visible_post
    )
    fk_effect_js = (
        f"""
  const fkTargets: Record<string, string> = {{{fk_targets_js}}};
  $effect(() => {{
    const fkAuto = silo.fkAutoFields('POST');
    for (const [field, target] of Object.entries(fkTargets)) {{
      if (fkAuto[field] === 'select') void registry.get(target).list();
    }}
  }});

  let fkFilterTerms = $state<Record<string, string>>({{}});

  function fkOptions(targetKey: string): {{id: string; label: string}}[] {{
    const targetSilo = registry.tryGet(targetKey);
    if (!targetSilo) return [];
    const labelFields = ((registry.meta as any)[targetKey]?.label_fields ?? []) as string[];
    const term = (fkFilterTerms[targetKey] ?? '').trim().toLowerCase();
    return targetSilo.items
      .map(item => ({{id: targetSilo.pkValue(item) ?? '', label: formatLabel(item, labelFields)}}))
      .filter(opt => opt.id !== '')
      .filter(opt => !term || opt.label.toLowerCase().includes(term));
  }}

  const fkFilterTimers: Record<string, ReturnType<typeof setTimeout>> = {{}};

  function onFkFilter(targetKey: string, term: string): void {{
    // Instant client-side narrowing of already-loaded options (like the list view's
    // localFilters), independent of the debounced server round-trip below.
    fkFilterTerms[targetKey] = term;

    const targetSilo = registry.tryGet(targetKey);
    if (!targetSilo) return;
    if (fkFilterTimers[targetKey]) clearTimeout(fkFilterTimers[targetKey]);
    fkFilterTimers[targetKey] = setTimeout(() => {{
      const labelFields = ((registry.meta as any)[targetKey]?.label_fields ?? []) as string[];
      const trimmed = term.trim();
      targetSilo.resetFilterState();
      const q = trimmed && labelFields.length
        ? labelFields.map((f: string) => `${{f}}:*${{trimmed}}`).join(',')
        : '';
      void targetSilo.list(q ? ({{q}} as any) : {{}}, 0);
    }}, 300);
  }}

  // Custom combobox (not a native <select>): keyed by field name, since several
  // fields could in principle target the same resource.
  let fkComboOpen = $state<Record<string, boolean>>({{}});
  let fkComboText = $state<Record<string, string>>({{}});

  function openFkCombo(field: string): void {{
    fkComboOpen[field] = true;
  }}

  function closeFkCombo(field: string): void {{
    // Delay so a (mousedown) selection on an option registers before blur closes the list.
    setTimeout(() => {{ fkComboOpen[field] = false; }}, 150);
  }}

  function onFkComboInput(field: string, targetKey: string, term: string): void {{
    fkComboText[field] = term;
    (form as any)[field] = '';
    fkComboOpen[field] = true;
    onFkFilter(targetKey, term);
  }}

  function selectFkOption(field: string, opt: {{id: string; label: string}}): void {{
    (form as any)[field] = opt.id;
    fkComboText[field] = opt.label;
    fkComboOpen[field] = false;
  }}"""
        if fk_targets_js else ''
    )
    return f"""\
<script lang="ts">
  import {{ registry }} from '$lib/generated/stores/silo-registry.svelte.ts';
  import {{ formatLabel }} from '$lib/generated/stores/silo-shared';
  import {{ goto }} from '$app/navigation';

  const silo = registry.get('{map_key}');
  let form = $state<Record<string, unknown>>({{ {fields_init} }});
  let error = $state('');

  const optionalFields = new Set([{optional_set_js}]);
  const textFields = new Set([{text_fields_js}]);
{fk_effect_js}

  async function handleSubmit(e: Event) {{
    e.preventDefault();
    try {{
      const payload = Object.fromEntries(
        Object.entries(form)
          .filter(([k]) => !silo.inaccessibleFields('POST').has(k))
          .filter(([k, v]) => !optionalFields.has(k) || v !== '')
          {_null_map_js()}
      );
      const urlParams = new URLSearchParams(window.location.search);
      for (const [field, rule] of Object.entries(silo.fkAutoFields('POST'))) {{
        if (rule === 'context') {{
          const val = urlParams.get(field);
          if (val != null) payload[field] = val;
        }}
      }}
      const res = await silo.create(payload);
      if (!res.ok) throw new Error(await res.text());
      const created = await res.json();
      silo.setItem(created);
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
    iname: str, pk_field: str, pk_info: list,
    out_names: list, fk_deps: list, all_fields: dict,
) -> str:
    fk_map = {lf: (rs, rt) for lf, rs, rt, _ in fk_deps}

    if pk_field and len(pk_info) > 1:
        _pk_url = '::'.join(f'{c}:${{item.{c}}}' for c, _, _ in pk_info)
    elif pk_field:
        _pk_url = f'{{item.{pk_field}}}'
    else:
        _pk_url = ''

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
                f'<div class="flex gap-2 items-baseline">{label}\n'
                f'  {{#if hidePk}}'
                f'<span class="font-mono text-xs text-gray-500 break-all">{{item.{f}}}</span>'
                f'{{:else}}'
                f'<a href="/ho_bo/{schema_name}/{table_name}/{_pk_url}"'
                f' class="font-mono text-xs text-blue-500 hover:underline break-all">{{item.{f}}}</a>'
                f'{{/if}}\n'
                f'</div>'
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

    rows = '\n  '.join(
        f'{{#if !inaccessibleFields.has(\'{f}\')}}\n  {_ro_row(f)}\n  {{/if}}'
        for f in out_names
    )

    return f"""\
<script lang="ts">{latex_import}
  import type {{ Row }} from '$lib/generated/stores/resource.silo.svelte.ts';

  let {{ item, hidePk = false, inaccessibleFields = new Set<string>() }}: {{ item: Row; hidePk?: boolean; inaccessibleFields?: Set<string> }} = $props();
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
        f"{{#if !silo.inaccessibleFields('PUT').has('{f}')}}\n    "
        + _svelte_form_field(f, all_fields)
        + '\n    {/if}'
        for f in visible_put
    ) if visible_put else ''

    # Form state + edit toggle — populated reactively from item once loaded
    extra_script = ''
    edit_btn     = ''
    edit_section = '\n  <Fields {item} inaccessibleFields={silo.inaccessibleFields()} />'

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
        put_text_fields_js = _text_fields(visible_put, all_fields)
        extra_script = (
            f'\n  let editing = $state(false);\n'
            f'  let form = $state<Record<string, unknown>>({{ {empty_init} }});\n'
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
            f'        Object.entries(form)\n'
            f"          .filter(([k]) => !silo.inaccessibleFields('PUT').has(k))\n"
            f'          {_null_map_js("putTextFields")}\n'
            f'      );\n'
            f'      const res = await silo.update(id, putPayload);\n'
            f'      if (!res.ok) throw new Error(await res.text());\n'
            f'      const updated = await res.json();\n'
            f'      silo.setItem(updated);\n'
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
  <Fields {{item}} inaccessibleFields={{silo.inaccessibleFields()}} />
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
    edit_btn_wrap = (
        f'\n      {{#if silo.canAccess(\'PUT\', id)}}{edit_btn}\n      {{/if}}'
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
            cn = _cname(rs, rt)
            lines.append(f"  import {cn}Fields from '$lib/generated/components/{s}/Fields.svelte';")
        return ('\n' + '\n'.join(lines)) if lines else ''

    def _lf_ref_name(lf: str) -> str:
        """user_fk → userFkRef  (always unique — keyed on local field, not remote table)"""
        parts = lf.split('_')
        return parts[0] + ''.join(p.capitalize() for p in parts[1:]) + 'Ref'

    def _fk_ref_states(deps: list) -> str:
        lines = []
        for lf, rs, rt, _ in deps:
            fk_key = f'{rs}/{rt}'
            lines.append(
                f"  let {_lf_ref_name(lf)} = $derived(item && item['{lf}'] ? "
                f"registry.tryGet('{fk_key}')?.byPk.get(String(item['{lf}'])) ?? null : null);"
            )
        return ('\n' + '\n'.join(lines)) if lines else ''

    def _fk_ref_effects(deps: list) -> str:
        blocks = []
        for lf, rs, rt, _ in deps:
            fk_key = f'{rs}/{rt}'
            blocks.append(
                f'  $effect(() => {{\n'
                f"    const _lf = item && item['{lf}'];\n"
                f'    if (!_lf) return;\n'
                f"    const _fk = registry.tryGet('{fk_key}');\n"
                f'    if (!_fk) return;\n'
                f'    const _url = _fk.getUrl(String(_lf));\n'
                f'    if (!auth.fetchedRoutes.has(_url)) void _fk.get(String(_lf));\n'
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
            f'    <a href="/ho_bo/{rs}/{rt}/{{{lf_ref}.{remote_pk}}}"'
            f' class="text-lg font-semibold hover:underline hover:text-blue-700">{_title(rs, rt)}</a>\n'
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
            f'    <a href="/ho_bo/{rs}/{rt}" class="text-lg font-semibold hover:underline hover:text-blue-700">{_title(rs, rt)}</a>\n'
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
  import {{ registry }} from '$lib/generated/stores/silo-registry.svelte.ts';
  import {{ goto }} from '$app/navigation';
  import {{ auth }} from '$lib/auth.svelte.ts';
  import {{ untrack }} from 'svelte';
  import Fields from '$lib/generated/components/{stem}/Fields.svelte';
  {fk_imports}{rev_imports}

  const silo = registry.get('{map_key}');
  let {{ id }}: {{ id: string }} = $props();
  let item = $derived(silo.byPk.get(id) ?? null);
{fk_states}
  $effect(() => {{
    void auth.token;
    void auth.accessVersion;
    void (auth.resourceAccessVersion as any)['{map_key}'];
    if (!item) untrack(() => void silo.get(id));
  }});

  $effect(() => {{
    if (item) untrack(() => silo.markRead(id));
  }});

  $effect(() => {{
    const ev = auth.lastEvent;
    if (ev?.resource === '{map_key}' && String(ev.id) === id && ev.event === 'delete')
      goto('/ho_bo/{schema_name}/{table_name}');
  }});
{fk_effects}{extra_script}
</script>

<div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-2 px-4 lg:h-[calc(100vh-4rem)] lg:overflow-hidden">
  <div class="min-w-0 lg:overflow-y-auto lg:pr-1">
    {{#if item}}
    <div class="p-6 bg-white rounded-lg shadow">
      <div class="flex justify-between items-start mb-6">
        <h1 class="text-2xl font-bold"><a href="/ho_bo/{schema_name}/{table_name}" class="hover:underline hover:text-blue-700">{title}</a></h1>
        <div class="flex gap-3 items-center">
{edit_btn_wrap}
          <button onclick={{() => history.back()}} class="text-sm text-gray-500 hover:underline">← Back</button>
        </div>
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

    def generate(self, classes, api_version, output_dir: Path, *, model=None) -> None:
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True)

        version_prefix = f'/v{api_version}' if api_version is not None else ''
        project_name = output_dir.name

        # --- static files ---
        self._write(output_dir / '.gitignore',
                    'node_modules/\nbuild/\n.svelte-kit/\n')
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

        # --- shared stores (resource silo + registry) ---
        stores_dir = output_dir / 'src' / 'lib' / 'generated' / 'stores'
        stores_dir.mkdir(parents=True, exist_ok=True)
        svelte_assets = Path(__file__).parent
        for fname in ('resource.silo.svelte.ts', 'silo-registry.svelte.ts'):
            shutil.copy2(svelte_assets / fname, stores_dir / fname)
            print(f'  {stores_dir / fname}')

        # --- shared Svelte components (permissions matrix) ---
        generated_dir = output_dir / 'src' / 'lib' / 'generated'
        for fname in ('PermissionsFields.svelte', 'PermissionsMatrix.svelte', 'Tooltip.svelte', 'NewItemsBadge.svelte'):
            shutil.copy2(svelte_assets / fname, generated_dir / fname)
            print(f'  {generated_dir / fname}')

        # --- cross-framework shared files (schema types / silo core logic / filters) ---
        frontend_dir = Path(__file__).parents[2]
        for fname in ('schema.types.ts', 'silo-shared.ts', 'templates_filters.ts'):
            src = frontend_dir / fname
            if src.exists():
                dest_name = 'filters.ts' if fname == 'templates_filters.ts' else fname
                shutil.copy2(src, stores_dir / dest_name)
                print(f'  {stores_dir / dest_name}')

        # --- stateRegistry + auth store + WS env var ---
        self._write(output_dir / 'src' / 'lib' / 'latex.ts', _LATEX_TS)
        self._write(output_dir / 'src' / 'lib' / 'stateRegistry.ts',
            "const _fns: Array<() => void> = [];\n"
            "const _keyFns = new Map<string, () => void>();\n"
            "export const registerClear = (fn: () => void): void => { _fns.push(fn); };\n"
            "export const registerClearForKey = (key: string, fn: () => void): void => { _keyFns.set(key, fn); };\n"
            "export const clearAllStates = (): void => { _fns.forEach(fn => fn()); };\n"
            "export const clearStateForKey = (key: string): void => { _keyFns.get(key)?.(); };\n"
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
                optional_post_fields, api_excluded,
            ))

        # --- static assets ---
        assets_src = Path(__file__).parents[3] / 'assets'
        static_dir = output_dir / 'static'
        static_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(assets_src / 'logo.png', static_dir / 'logo.png')
        shutil.copy2(assets_src / 'logo-chapeau.png', static_dir / 'logo-chapeau.png')

        # --- layout + home ---
        routes_dir     = output_dir / 'src' / 'routes'
        components_dir = output_dir / 'src' / 'lib' / 'generated' / 'components'
        # Root layout is minimal — home page renders without nav
        self._write(routes_dir / '+layout.svelte',
                    '<script>\n  import \'../app.css\';\n  let { children } = $props();\n</script>\n{@render children()}\n')
        # (nav) group provides the sidebar layout for all other pages
        self._write(routes_dir / '(nav)' / '+layout.svelte', _layout(resources, version_prefix))
        self._write(routes_dir / '(nav)' / 'ho_bo' / '+layout.svelte', _admin_layout())
        # +layout.ts ensures registry.init() completes before any component renders
        self._write(routes_dir / '(nav)' / '+layout.ts',
                    f"import {{ browser }} from '$app/environment';\n"
                    f"import {{ registry }} from '$lib/generated/stores/silo-registry.svelte.ts';\n\n"
                    f"export const ssr = false;\n\n"
                    f"export async function load() {{\n"
                    f"  if (browser) await registry.init('{version_prefix}');\n"
                    f"  return {{}};\n"
                    f"}}\n")
        first_route = (
            f'/ho_bo/{resources[0][0]}/{resources[0][1]}' if resources else '/ho_bo'
        )
        self._write(routes_dir / '+page.svelte', _home_page(), once=True)
        self._write(routes_dir / '(nav)' / 'ho_bo' / '+page.svelte', _login_page(version_prefix))
        self._write(routes_dir / '(nav)' / 'login'  / '+page.svelte', _login_page(version_prefix))
        self._write(routes_dir / '(nav)' / 'access' / '+page.svelte', _access_page(version_prefix))
        self._write(routes_dir / '(nav)' / 'schema' / '+page.svelte', _schema_page_svelte(), once=True)
        self._write(routes_dir / '(nav)' / 'ho_bo' / 'search' / '+page.svelte',
                    _search_page_svelte(version_prefix))
        self._write(routes_dir / 'auth' / 'callback' / '+page.svelte', _auth_callback_page())
        self._write(routes_dir / 'auth' / 'delegate' / '+page.svelte', _auth_delegate_page(version_prefix))

        # --- per-resource components + routes ---
        for (schema_name, table_name, stem, rname, iname,
             out_names, pk_info, pk_field, all_fields,
             has_post, has_put, has_del,
             post_in_names, put_in_names, map_key, crud_access, fk_deps, rev_fk_deps,
             optional_post_fields, api_excluded) in resources:

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
                              post_in_names, all_fields, optional_post_fields,
                              fk_deps=fk_deps),
                )
                self._write(res_dir / 'new' / '+page.svelte', _new_page_wrapper(stem))

            # DetailView component + thin page wrapper
            if pk_info and 'GET' in crud_access:
                self._write(
                    comp_dir / 'Fields.svelte',
                    _fields_component_svelte(schema_name, table_name, iname,
                                             pk_field, pk_info, out_names, fk_deps, all_fields),
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
