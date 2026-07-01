def _ho_admin_component_ts(version_prefix: str) -> str:
    return f"""\
import {{ Component, OnInit, computed, inject, signal }} from '@angular/core';
import {{ Router }} from '@angular/router';
import {{ AuthService }} from '../../core/auth.service';

interface FilterInfo  {{ id: string; name: string; }}
interface FkDep {{ fields: string[]; target: string; target_fields: string[]; }}
interface AccessEntry {{
  id: string;
  in: string[];
  out: string[];
  fk_auto: Record<string, 'connected_user' | 'context' | 'select'>;
  active_filters: string[];
  searchable: string[];
}}
interface ResourceInfo {{
  fields: string[];
  pk_fields: string[];
  fields_with_defaults: string[];
  fk_deps: FkDep[];
  dynamic_roles: string[];
  filters: FilterInfo[];
  access: Record<string, Record<string, AccessEntry>>;
}}
interface RoleInfo {{ name: string; deletable: boolean; kind: 'system' | 'dynamic' | 'user'; parent_name: string | null; }}
type Catalog = Record<string, ResourceInfo>;

const VERB_COLOR: Record<string, string> = {{
  GET:    'text-blue-600',
  POST:   'text-green-600',
  PUT:    'text-yellow-600',
  DELETE: 'text-red-500',
}};

@Component({{
  selector: 'app-ho-admin',
  standalone: true,
  template: `
    <div class="flex h-full gap-0 -m-6">

      <!-- Left: role list -->
      <div class="w-52 shrink-0 border-r bg-white flex flex-col h-full">
        <div class="px-4 py-3 border-b flex items-center justify-between">
          <h2 class="text-xs font-semibold text-gray-400 uppercase tracking-wide">Roles</h2>
          <button (click)="showNewRole.set(!showNewRole())"
                  class="text-xs text-blue-600 hover:text-blue-800 font-semibold">+</button>
        </div>
        @if (showNewRole()) {{
          <div class="px-3 py-2 border-b bg-gray-50 space-y-1.5">
            <input [value]="newRoleName()" (input)="newRoleName.set($any($event.target).value)"
                   placeholder="Role name" class="w-full text-xs border rounded px-2 py-1" />
            <select [value]="newRoleParent()" (change)="newRoleParent.set($any($event.target).value)"
                    class="w-full text-xs border rounded px-2 py-1">
              @for (r of roles(); track r.name) {{
                <option [value]="r.name">{{{{ r.name }}}}</option>
              }}
            </select>
            <button (click)="createRole()"
                    class="w-full text-xs bg-blue-600 text-white rounded py-1 hover:bg-blue-700">Create</button>
          </div>
        }}
        <div class="flex-1 overflow-y-auto px-2 py-2 space-y-0.5">
          @for (r of roles(); track r.name) {{
            <div class="group relative">
              <button (click)="selectRole(r.name)"
                      class="w-full text-left px-3 py-1.5 rounded text-sm transition-colors"
                      [class]="selectedRole() === r.name
                        ? 'bg-blue-600 text-white'
                        : 'text-gray-700 hover:bg-gray-100'">
                <div class="flex items-center justify-between gap-1">
                  <span>{{{{ r.name }}}}</span>
                  <div class="flex items-center gap-1">
                    @if (r.kind === 'system') {{
                      <span class="text-[10px] px-1.5 rounded"
                            [class]="selectedRole() === r.name ? 'bg-blue-500 text-white' : 'bg-gray-100 text-gray-500'">sys</span>
                    }} @else if (r.kind === 'dynamic') {{
                      <span class="text-[10px] px-1.5 rounded"
                            [class]="selectedRole() === r.name ? 'bg-blue-500 text-white' : 'bg-purple-100 text-purple-600'">dyn</span>
                    }} @else {{
                      <button (click)="$event.stopPropagation(); deleteRole(r.name)"
                              class="text-[10px] px-1 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                              [class]="selectedRole() === r.name ? 'text-blue-200 hover:text-white' : 'text-gray-400 hover:text-red-500'"
                              title="Delete role">✕</button>
                    }}
                  </div>
                </div>
                @if (r.parent_name) {{
                  <div class="text-[10px] opacity-60 mt-0.5">↳ {{{{ r.parent_name }}}}</div>
                }}
              </button>
            </div>
          }}
        </div>
      </div>

      <!-- Centre: access matrix with inline field editors -->
      <div class="flex-1 overflow-y-auto p-6">
        @if (!selectedRole()) {{
          <p class="text-gray-400 text-sm mt-16 text-center">Select a role to manage its access rights.</p>
        }} @else if (loading()) {{
          <p class="text-gray-400 text-sm mt-16 text-center">Loading…</p>
        }} @else {{
          <h1 class="text-xl font-bold mb-5">
            Access rights —
            <span class="text-blue-600">{{{{ selectedRole() }}}}</span>
          </h1>
          <div class="space-y-3">
            @for (entry of catalogEntries(); track entry[0]) {{
              <div class="bg-white rounded-lg shadow-sm overflow-hidden">

                <!-- Resource header -->
                <div class="px-4 py-2 bg-gray-50 border-b flex items-center gap-2">
                  <span class="font-mono text-sm font-semibold text-gray-700">{{{{ entry[0] }}}}</span>
                </div>

                <!-- Verb checkboxes -->
                <div class="px-4 py-3 flex gap-5 flex-wrap items-start">
                  @for (verb of verbs; track verb) {{
                    @let acc = getAccess(entry[0], verb);
                    @let inherited = isInherited(entry[0], verb);
                    @let blocked = hasAncestorVerb(entry[0], verb);
                    @let hasAccess = !!(acc || inherited);
                    <div class="flex flex-col items-center gap-0.5 min-w-[52px]">
                      <label class="flex items-center gap-1.5 select-none" [class]="blocked ? 'cursor-default opacity-60' : 'cursor-pointer'">
                        <input type="checkbox" [checked]="hasAccess"
                               [disabled]="blocked"
                               (change)="!blocked && toggleAccess(entry[0], verb, !acc)"
                               class="rounded border-gray-300">
                        <span class="text-xs font-mono font-semibold" [class]="verbColor(verb)">{{{{ verb }}}}</span>
                        @if (acc && hasConfigIssue(entry[0], verb) && !blocked) {{
                          <span class="text-amber-500 text-xs" title="No fields configured — requests will return 403">⚠</span>
                        }}
                      </label>
                      @if (inherited) {{
                        <span class="text-[9px] text-gray-400">↑ {{{{ getInheritedAccess(entry[0], verb)!.from }}}}</span>
                      }}
                      @if (hasAccess && verb !== 'DELETE') {{
                        <button (click)="openPanel(entry[0], verb)"
                                class="text-[10px] leading-tight transition-colors"
                                [class]="isPanel(entry[0], verb)
                                  ? 'text-blue-600 font-semibold'
                                  : 'text-blue-400 hover:text-blue-600 underline'">
                          {{{{ isPanel(entry[0], verb) ? '▲ fields' : '▼ fields' }}}}
                        </button>
                      }}
                    </div>
                  }}
                </div>

                <!-- Inline field/filter editor — shown below the verb row for this resource -->
                @if (isPanel(entry[0], panel()?.verb ?? '') && panelEffectiveAccess() && panelInfo()) {{
                  <div class="border-t bg-gray-50 px-5 py-4">
                    <div class="flex items-center justify-between mb-4">
                      <span class="text-xs font-semibold text-gray-500">
                        <span [class]="verbColor(panel()!.verb)">{{{{ panel()!.verb }}}}</span>
                        — field access
                      </span>
                      <button (click)="panel.set(null)"
                              class="text-gray-400 hover:text-gray-600 leading-none text-base">✕</button>
                    </div>

                    <div class="flex gap-8 flex-wrap items-start">

                      <!-- In fields (POST / PUT) -->
                      @if (panel()!.verb === 'POST' || panel()!.verb === 'PUT') {{
                        <div class="min-w-[140px]">
                          <div class="flex items-center gap-3 mb-2">
                            <div class="text-[10px] font-bold uppercase tracking-widest text-blue-500">In <span class="normal-case font-normal opacity-70">client → api</span></div>
                            @if (!panelInheritedFrom()) {{
                              <button (click)="addAllFields('in')"
                                      class="text-[10px] px-1.5 py-0.5 rounded border border-blue-200 text-blue-500 hover:bg-blue-50">all</button>
                            }}
                          </div>
                          <div class="space-y-1">
                            @for (f of panelInfo()!.fields; track f) {{
                              <label class="flex items-center gap-2 text-xs" [class]="panelInheritedFrom() ? 'cursor-default' : 'cursor-pointer'">
                                <input type="checkbox"
                                       [checked]="panelEffectiveAccess()!.in.includes(f) || isInheritedField(f, 'in')"
                                       [disabled]="!!panelInheritedFrom() || isInheritedField(f, 'in') || panelInfo()!.fields_with_defaults.includes(f)"
                                       (change)="!panelInheritedFrom() && !isInheritedField(f, 'in') && toggleField(f, 'in', !panelAccess()!.in.includes(f))"
                                       class="rounded border-gray-300 text-blue-600 w-3 h-3">
                                <span class="font-mono"
                                      [class]="panelInfo()!.fields_with_defaults.includes(f) ? 'text-gray-400' : (panelAccess()?.fk_auto?.[f] ? 'text-purple-600' : 'text-gray-700')">{{{{ f }}}}</span>
                                @if (panelInfo()!.fields_with_defaults.includes(f)) {{
                                  <span class="text-[9px] bg-gray-100 text-gray-400 px-1 rounded" title="Server-generated — cannot be set in forms">auto</span>
                                }} @else if (panelAccess()?.fk_auto?.[f]) {{
                                  <span class="text-[9px] bg-purple-50 text-purple-500 px-1 rounded">{{{{ panelAccess()!.fk_auto[f] }}}}</span>
                                }}
                              </label>
                            }}
                          </div>
                          @if (fkGroupsInPanel().length > 0) {{
                            <div class="mt-3 space-y-2">
                              <div class="text-[9px] font-bold uppercase tracking-widest text-purple-400 mb-1">FK auto-resolve</div>
                              @for (fk of fkGroupsInPanel(); track fk.target) {{
                                <div class="border-l-2 border-purple-200 pl-2">
                                  <div class="flex items-center gap-2 mb-0.5">
                                    <span class="text-[9px] text-purple-500 font-semibold">→ {{{{ fk.target }}}}</span>
                                    @if (!panelInheritedFrom()) {{
                                      <select class="text-[9px] border rounded px-1 py-0 leading-tight"
                                              [value]="getFkAutoRule(fk.fields)"
                                              (change)="setFkAutoGroup(fk.fields, $any($event.target).value)">
                                        <option value="">—</option>
                                        <option value="connected_user">connected_user</option>
                                        <option value="context">context</option>
                                        <option value="select">select</option>
                                      </select>
                                    }} @else {{
                                      <span class="text-[9px] text-purple-400">{{{{ getFkAutoRule(fk.fields) || '—' }}}}</span>
                                    }}
                                  </div>
                                  @for (f of fk.fields; track f) {{
                                    <span class="text-[9px] font-mono text-purple-400 mr-1">{{{{ f }}}}</span>
                                  }}
                                </div>
                              }}
                            </div>
                          }}
                        </div>
                      }}

                      <!-- Out fields -->
                      <div class="min-w-[140px]">
                        <div class="flex items-center gap-3 mb-2">
                          <div class="text-[10px] font-bold uppercase tracking-widest text-emerald-500">Out <span class="normal-case font-normal opacity-70">api → client</span></div>
                          @if (!panelInheritedFrom()) {{
                            <button (click)="addAllFields('out')"
                                    class="text-[10px] px-1.5 py-0.5 rounded border border-emerald-200 text-emerald-500 hover:bg-emerald-50">all</button>
                          }}
                        </div>
                        <div class="space-y-1">
                          @for (f of panelInfo()!.fields; track f) {{
                            @let isPk = panel()!.verb === 'GET' && panelInfo()!.pk_fields.includes(f);
                            <label class="flex items-center gap-2 text-xs"
                                   [class]="(panelInheritedFrom() || isPk) ? 'cursor-default' : 'cursor-pointer'">
                              <input type="checkbox"
                                     [checked]="isPk || panelEffectiveAccess()!.out.includes(f) || isInheritedField(f, 'out')"
                                     [disabled]="isPk || !!panelInheritedFrom() || isInheritedField(f, 'out')"
                                     (change)="!isPk && !panelInheritedFrom() && !isInheritedField(f, 'out') && toggleField(f, 'out', !panelAccess()!.out.includes(f))"
                                     class="rounded border-gray-300 text-emerald-600 w-3 h-3">
                              <span class="font-mono text-gray-700">{{{{ f }}}}</span>
                              @if (isPk) {{
                                <span class="text-[9px] bg-blue-50 text-blue-400 px-1 rounded" title="Primary key — always included in GET">pk</span>
                              }} @else if (panelInfo()!.fields_with_defaults.includes(f)) {{
                                <span class="text-[9px] bg-gray-100 text-gray-400 px-1 rounded" title="Has DB default">auto</span>
                              }}
                            </label>
                          }}
                        </div>
                      </div>

                      <!-- Searchable fields (GET only) -->
                      @if (panel()!.verb === 'GET') {{
                        <div class="min-w-[140px]">
                          <div class="text-[10px] font-bold uppercase tracking-widest text-teal-500 mb-2">Searchable</div>
                          <div class="space-y-1">
                            @for (f of panelInfo()!.fields; track f) {{
                              @if (!panelInfo()!.pk_fields.includes(f) && panelEffectiveAccess()!.out.includes(f)) {{
                                <label class="flex items-center gap-2 text-xs" [class]="panelInheritedFrom() ? 'cursor-default' : 'cursor-pointer'">
                                  <input type="checkbox"
                                         [checked]="panelAccess()!.searchable.includes(f)"
                                         [disabled]="!!panelInheritedFrom()"
                                         (change)="!panelInheritedFrom() && toggleSearchable(f, !panelAccess()!.searchable.includes(f))"
                                         class="rounded border-gray-300 text-teal-600 w-3 h-3">
                                  <span class="font-mono text-gray-700">{{{{ f }}}}</span>
                                </label>
                              }}
                            }}
                          </div>
                        </div>
                      }}

                      <!-- Filters (GET only) -->
                      @if (panel()!.verb === 'GET' && panelInfo()!.filters.length > 0) {{
                        <div class="min-w-[140px]">
                          <div class="text-[10px] font-bold uppercase tracking-widest text-violet-500 mb-2">Filters</div>
                          <div class="space-y-1">
                            @for (fi of panelInfo()!.filters; track fi.id) {{
                              <label class="flex items-center gap-2 text-xs cursor-pointer">
                                <input type="checkbox"
                                       [checked]="panelAccess()!.active_filters.includes(fi.id)"
                                       (change)="toggleFilter(fi.id, !panelAccess()!.active_filters.includes(fi.id))"
                                       class="rounded border-gray-300 text-violet-600 w-3 h-3">
                                <span class="font-mono text-gray-700">{{{{ fi.name }}}}</span>
                              </label>
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
        }}
      </div>

    </div>
  `,
}})
export class HoAdminComponent implements OnInit {{
  private auth   = inject(AuthService);
  private router = inject(Router);

  readonly catalog      = signal<Catalog>({{}});
  readonly roles        = signal<RoleInfo[]>([]);
  readonly loading      = signal(true);
  readonly selectedRole = signal<string | null>(null);
  readonly panel        = signal<{{resource: string; verb: string}} | null>(null);
  readonly showNewRole  = signal(false);
  readonly newRoleName  = signal('');
  readonly newRoleParent = signal('connected');

  readonly verbs = ['GET', 'POST', 'PUT', 'DELETE'] as const;

  readonly catalogEntries = computed(() => {{
    const role = this.selectedRole();
    const entries = Object.entries(this.catalog()).sort((a, b) => a[0].localeCompare(b[0]));
    if (!role) return entries;
    const roleInfo = this.roles().find(r => r.name === role);
    if (roleInfo?.kind === 'dynamic') {{
      return entries.filter(([, info]) => (info as ResourceInfo).dynamic_roles.includes(role));
    }}
    return entries;
  }});

  readonly parentMap = computed(() =>
    Object.fromEntries(this.roles().map(r => [r.name, r.parent_name ?? null]))
  );

  readonly ancestorChain = computed<string[]>(() => {{
    const role = this.selectedRole();
    if (!role) return [];
    const pm = this.parentMap();
    const chain: string[] = [];
    let cur: string | null = pm[role] ?? null;
    while (cur) {{ chain.push(cur); cur = pm[cur] ?? null; }}
    return chain;
  }});

  readonly panelAccess = computed<AccessEntry | undefined>(() => {{
    const p = this.panel();
    const role = this.selectedRole();
    if (!p || !role) return undefined;
    return this.catalog()[p.resource]?.access?.[p.verb]?.[role];
  }});

  readonly panelEffectiveAccess = computed<AccessEntry | undefined>(() => {{
    const own = this.panelAccess();
    if (own) return own;
    const p = this.panel();
    if (!p) return undefined;
    return this.getMergedAncestorAccess(p.resource, p.verb) ?? undefined;
  }});

  readonly panelInheritedFrom = computed<string | null>(() => {{
    const p = this.panel();
    if (!p || this.panelAccess()) return null;
    return this.getInheritedAccess(p.resource, p.verb)?.from ?? null;
  }});

  readonly panelInheritedEntry = computed<AccessEntry | undefined>(() => {{
    const p = this.panel();
    if (!p) return undefined;
    return this.getMergedAncestorAccess(p.resource, p.verb) ?? undefined;
  }});

  readonly panelInfo = computed<ResourceInfo | undefined>(() => {{
    const p = this.panel();
    return p ? this.catalog()[p.resource] : undefined;
  }});

  async ngOnInit(): Promise<void> {{
    if (this.auth.token() && this.auth.users().length === 0) {{
      await this.auth._fetchUsers();
    }}
    if (!this.auth.isAdmin()) {{
      void this.router.navigate(['/ho_bo']);
      return;
    }}
    void this._load();
  }}

  private get _hdrs(): Record<string, string> {{
    const t = this.auth.token();
    return t ? {{Authorization: `Bearer ${{t}}`}} : {{}};
  }}

  private async _load(): Promise<void> {{
    this.loading.set(true);
    const [catRes, rolesRes] = await Promise.all([
      fetch('{version_prefix}/ho_admin/catalog', {{headers: this._hdrs}}),
      fetch('{version_prefix}/ho_admin/roles',   {{headers: this._hdrs}}),
    ]);
    if (catRes.ok)   this.catalog.set(await catRes.json() as Catalog);
    if (rolesRes.ok) this.roles.set(await rolesRes.json() as RoleInfo[]);
    this.loading.set(false);
  }}

  private async _reloadCatalog(): Promise<void> {{
    const [catRes] = await Promise.all([
      fetch('{version_prefix}/ho_admin/catalog', {{headers: this._hdrs}}),
      this.auth._fetchAccess(),
    ]);
    if (catRes.ok) this.catalog.set(await catRes.json() as Catalog);
  }}

  getAccess(resource: string, verb: string): AccessEntry | undefined {{
    const role = this.selectedRole();
    return role ? this.catalog()[resource]?.access?.[verb]?.[role] : undefined;
  }}

  getInheritedAccess(resource: string, verb: string): {{entry: AccessEntry; from: string}} | null {{
    for (const anc of this.ancestorChain()) {{
      const e = this.catalog()[resource]?.access?.[verb]?.[anc];
      if (e) return {{entry: e, from: anc}};
    }}
    return null;
  }}

  getMergedAncestorAccess(resource: string, verb: string): AccessEntry | null {{
    let found = false;
    const ins  = new Set<string>();
    const outs = new Set<string>();
    const filters = new Set<string>();
    const searchable = new Set<string>();
    const fk_auto: Record<string, 'connected_user' | 'context' | 'select'> = {{}};
    for (const anc of this.ancestorChain()) {{
      const e = this.catalog()[resource]?.access?.[verb]?.[anc];
      if (!e) continue;
      found = true;
      e.in.forEach(f  => ins.add(f));
      e.out.forEach(f => outs.add(f));
      e.active_filters.forEach(f => filters.add(f));
      (e.searchable ?? []).forEach(f => searchable.add(f));
      Object.assign(fk_auto, e.fk_auto ?? {{}});
    }}
    if (!found) return null;
    return {{ id: '', in: [...ins], out: [...outs], fk_auto, active_filters: [...filters], searchable: [...searchable] }};
  }}

  isInherited(resource: string, verb: string): boolean {{
    return !this.getAccess(resource, verb) && !!this.getInheritedAccess(resource, verb);
  }}

  hasAncestorVerb(resource: string, verb: string): boolean {{
    return !!this.getInheritedAccess(resource, verb);
  }}

  verbColor(verb: string): string {{
    return VERB_COLOR[verb] ?? 'text-gray-600';
  }}

  hasConfigIssue(resource: string, verb: string): boolean {{
    const acc = this.getAccess(resource, verb);
    if (!acc || verb === 'DELETE') return false;
    if (verb === 'GET')  return acc.out.length === 0;
    if (verb === 'POST') return acc.in.length  === 0;
    if (verb === 'PUT')  return acc.in.length  === 0 || acc.out.length === 0;
    return false;
  }}

  isPanel(resource: string, verb: string): boolean {{
    const p = this.panel();
    return p?.resource === resource && p?.verb === verb;
  }}

  async openPanel(resource: string, verb: string): Promise<void> {{
    if (this.isPanel(resource, verb)) {{
      this.panel.set(null);
      return;
    }}
    if (this.isInherited(resource, verb)) {{
      await this.overrideVerb(resource, verb);
    }} else {{
      this.panel.set({{resource, verb}});
    }}
  }}

  selectRole(name: string): void {{
    this.panel.set(null);
    this.selectedRole.set(name);
  }}

  async createRole(): Promise<void> {{
    const name = this.newRoleName().trim();
    if (!name) return;
    await fetch('{version_prefix}/ho_admin/roles', {{
      method: 'POST',
      headers: {{...this._hdrs, 'Content-Type': 'application/json'}},
      body: JSON.stringify({{name, parent_name: this.newRoleParent()}}),
    }});
    this.newRoleName.set('');
    this.showNewRole.set(false);
    const res = await fetch('{version_prefix}/ho_admin/roles', {{headers: this._hdrs}});
    if (res.ok) this.roles.set(await res.json() as RoleInfo[]);
  }}

  async deleteRole(name: string): Promise<void> {{
    if (!confirm(`Delete role "${{name}}"?`)) return;
    await fetch(`{version_prefix}/ho_admin/roles/${{name}}`, {{
      method: 'DELETE', headers: this._hdrs,
    }});
    if (this.selectedRole() === name) this.selectedRole.set(null);
    const res = await fetch('{version_prefix}/ho_admin/roles', {{headers: this._hdrs}});
    if (res.ok) this.roles.set(await res.json() as RoleInfo[]);
  }}

  isInheritedField(field: string, dir: 'in' | 'out'): boolean {{
    const inh = this.panelInheritedEntry();
    if (!inh) return false;
    return dir === 'out' ? inh.out.includes(field) : inh.in.includes(field);
  }}

  async overrideVerb(resource: string, verb: string): Promise<void> {{
    await this.toggleAccess(resource, verb, true);
  }}

  async toggleAccess(resource: string, verb: string, enable: boolean): Promise<void> {{
    const role = this.selectedRole();
    if (!role) return;
    const acc = this.getAccess(resource, verb);
    if (enable) {{
      const [schema_name, table_name] = resource.split('/');
      await fetch('{version_prefix}/ho_admin/access', {{
        method: 'POST',
        headers: {{...this._hdrs, 'Content-Type': 'application/json'}},
        body: JSON.stringify({{role_name: role, schema_name, table_name, verb}}),
      }});
      await this._reloadCatalog();
      if (verb !== 'DELETE') this.panel.set({{resource, verb}});
      return;
    }} else if (acc) {{
      await fetch(`{version_prefix}/ho_admin/access/${{acc.id}}`, {{
        method: 'DELETE', headers: this._hdrs,
      }});
      if (this.isPanel(resource, verb)) this.panel.set(null);
    }}
    await this._reloadCatalog();
  }}

  async addAllFields(dir: 'in' | 'out'): Promise<void> {{
    const acc  = this.panelAccess();
    const info = this.panelInfo();
    if (!acc || !info) return;
    const existing = dir === 'in' ? acc.in : acc.out;
    const toAdd = info.fields.filter(f =>
      !this.isInheritedField(f, dir) &&
      !existing.includes(f) &&
      !(dir === 'in' && info.fields_with_defaults.includes(f)) &&
      !(dir === 'out' && this.panel()!.verb === 'GET' && info.pk_fields.includes(f))
    );
    if (toAdd.length === 0) return;
    const endpoint = dir === 'in' ? 'field_access_in' : 'field_access_out';
    await fetch(`{version_prefix}/ho_admin/${{endpoint}}/batch`, {{
      method: 'POST',
      headers: {{...this._hdrs, 'Content-Type': 'application/json'}},
      body: JSON.stringify({{access_id: acc.id, field_names: toAdd}}),
    }});
    await this._reloadCatalog();
  }}

  async toggleField(field: string, dir: 'in' | 'out', add: boolean): Promise<void> {{
    const acc = this.panelAccess();
    if (!acc) return;
    const endpoint = dir === 'in' ? 'field_access_in' : 'field_access_out';
    if (add) {{
      await fetch(`{version_prefix}/ho_admin/${{endpoint}}`, {{
        method: 'POST',
        headers: {{...this._hdrs, 'Content-Type': 'application/json'}},
        body: JSON.stringify({{access_id: acc.id, field_name: field}}),
      }});
    }} else {{
      await fetch(`{version_prefix}/ho_admin/${{endpoint}}/${{acc.id}}/${{field}}`, {{
        method: 'DELETE', headers: this._hdrs,
      }});
    }}
    await this._reloadCatalog();
  }}

  async toggleFilter(filterId: string, add: boolean): Promise<void> {{
    const acc = this.panelAccess();
    if (!acc) return;
    if (add) {{
      await fetch('{version_prefix}/ho_admin/access_filter', {{
        method: 'POST',
        headers: {{...this._hdrs, 'Content-Type': 'application/json'}},
        body: JSON.stringify({{access_id: acc.id, filter_id: filterId}}),
      }});
    }} else {{
      await fetch(`{version_prefix}/ho_admin/access_filter/${{acc.id}}/${{filterId}}`, {{
        method: 'DELETE', headers: this._hdrs,
      }});
    }}
    await this._reloadCatalog();
  }}

  async toggleSearchable(fieldName: string, add: boolean): Promise<void> {{
    const acc = this.panelAccess();
    if (!acc) return;
    if (add) {{
      await fetch('{version_prefix}/ho_admin/field_access_searchable', {{
        method: 'POST',
        headers: {{...this._hdrs, 'Content-Type': 'application/json'}},
        body: JSON.stringify({{access_id: acc.id, field_name: fieldName}}),
      }});
    }} else {{
      await fetch(`{version_prefix}/ho_admin/field_access_searchable/${{acc.id}}/${{fieldName}}`, {{
        method: 'DELETE', headers: this._hdrs,
      }});
    }}
    await this._reloadCatalog();
  }}

  readonly fkGroupsInPanel = computed<FkDep[]>(() => {{
    const p = this.panel();
    const info = this.panelInfo();
    const acc = this.panelEffectiveAccess();
    if (!p || !info || !acc || p.verb === 'GET' || p.verb === 'DELETE') return [];
    const inSet = new Set(acc.in);
    return (info.fk_deps ?? []).filter(fk => fk.fields.some(f => inSet.has(f)));
  }});

  getFkAutoRule(fields: string[]): string {{
    const fkAuto = this.panelAccess()?.fk_auto ?? {{}};
    return fkAuto[fields[0]] ?? '';
  }}

  async setFkAutoGroup(fields: string[], rule: string): Promise<void> {{
    const acc = this.panelAccess();
    if (!acc) return;
    for (const field of fields) {{
      if (!rule) {{
        await fetch(`{version_prefix}/ho_admin/field_access_fk_auto/${{acc.id}}/${{field}}`, {{
          method: 'DELETE', headers: this._hdrs,
        }});
      }} else {{
        await fetch('{version_prefix}/ho_admin/field_access_fk_auto', {{
          method: 'POST',
          headers: {{...this._hdrs, 'Content-Type': 'application/json'}},
          body: JSON.stringify({{access_id: acc.id, field_name: field, resolve_rule: rule}}),
        }});
      }}
    }}
    await this._reloadCatalog();
  }}
}}
"""
