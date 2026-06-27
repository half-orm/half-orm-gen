def _ho_admin_component_ts(version_prefix: str) -> str:
    return f"""\
import {{ Component, OnInit, computed, inject, signal }} from '@angular/core';
import {{ Router }} from '@angular/router';
import {{ AuthService }} from '../../core/auth.service';

interface FilterInfo  {{ id: string; name: string; }}
interface AccessEntry {{
  id: string;
  all_fields_in: boolean;
  all_fields_out: boolean;
  in: string[];
  out: string[];
  active_filters: string[];
}}
interface ResourceInfo {{
  fields: string[];
  pk_fields: string[];
  fields_with_defaults: string[];
  dynamic_roles: string[];
  filters: FilterInfo[];
  access: Record<string, Record<string, AccessEntry>>;
}}
interface RoleInfo {{ name: string; deletable: boolean; kind: 'system' | 'dynamic' | 'user'; }}
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
        <div class="px-4 py-3 border-b">
          <h2 class="text-xs font-semibold text-gray-400 uppercase tracking-wide">Roles</h2>
        </div>
        <div class="flex-1 overflow-y-auto px-2 py-2 space-y-0.5">
          @for (r of roles(); track r.name) {{
            <button (click)="selectRole(r.name)"
                    class="w-full text-left px-3 py-2 rounded text-sm transition-colors flex items-center justify-between gap-1"
                    [class]="selectedRole() === r.name
                      ? 'bg-blue-600 text-white'
                      : 'text-gray-700 hover:bg-gray-100'">
              <span>{{{{ r.name }}}}</span>
              @if (r.kind === 'system') {{
                <span class="text-[10px] px-1.5 rounded"
                      [class]="selectedRole() === r.name ? 'bg-blue-500 text-white' : 'bg-gray-100 text-gray-500'">sys</span>
              }} @else if (r.kind === 'dynamic') {{
                <span class="text-[10px] px-1.5 rounded"
                      [class]="selectedRole() === r.name ? 'bg-blue-500 text-white' : 'bg-purple-100 text-purple-600'">dyn</span>
              }}
            </button>
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
                  @for (dr of entry[1].dynamic_roles; track dr) {{
                    <span class="text-[10px] px-2 py-0.5 rounded-full bg-purple-100 text-purple-600">{{{{ dr }}}}</span>
                  }}
                </div>

                <!-- Verb checkboxes -->
                <div class="px-4 py-3 flex gap-5 flex-wrap items-start">
                  @for (verb of verbs; track verb) {{
                    @let acc = getAccess(entry[0], verb);
                    <div class="flex flex-col items-center gap-0.5 min-w-[52px]">
                      <label class="flex items-center gap-1.5 cursor-pointer select-none">
                        <input type="checkbox" [checked]="!!acc"
                               (change)="toggleAccess(entry[0], verb, !acc)"
                               class="rounded border-gray-300">
                        <span class="text-xs font-mono font-semibold" [class]="verbColor(verb)">{{{{ verb }}}}</span>
                        @if (acc && hasConfigIssue(entry[0], verb)) {{
                          <span class="text-amber-500 text-xs" title="No fields configured — requests will return 403">⚠</span>
                        }}
                      </label>
                      @if (acc && verb !== 'DELETE') {{
                        <button (click)="togglePanel(entry[0], verb)"
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
                @if (isPanel(entry[0], panel()?.verb ?? '') && panelAccess() && panelInfo()) {{
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
                            <label class="flex items-center gap-1 text-[10px] text-gray-500 cursor-pointer">
                              <input type="checkbox" [checked]="panelAccess()!.all_fields_in"
                                     (change)="updateAllFields('in', !panelAccess()!.all_fields_in)"
                                     class="rounded border-gray-300 text-blue-600 w-3 h-3">
                              all
                            </label>
                          </div>
                          <div class="space-y-1">
                            @for (f of panelInfo()!.fields; track f) {{
                              <label class="flex items-center gap-2 text-xs cursor-pointer">
                                <input type="checkbox"
                                       [checked]="panelAccess()!.all_fields_in || panelAccess()!.in.includes(f)"
                                       [disabled]="panelAccess()!.all_fields_in || panelInfo()!.fields_with_defaults.includes(f)"
                                       (change)="toggleField(f, 'in', !panelAccess()!.in.includes(f))"
                                       class="rounded border-gray-300 text-blue-600 w-3 h-3">
                                <span class="font-mono"
                                      [class]="panelInfo()!.fields_with_defaults.includes(f) ? 'text-gray-400' : 'text-gray-700'">{{{{ f }}}}</span>
                                @if (panelInfo()!.fields_with_defaults.includes(f)) {{
                                  <span class="text-[9px] bg-gray-100 text-gray-400 px-1 rounded" title="Has DB default — won't appear in forms">auto</span>
                                }}
                              </label>
                            }}
                          </div>
                        </div>
                      }}

                      <!-- Out fields -->
                      <div class="min-w-[140px]">
                        <div class="flex items-center gap-3 mb-2">
                          <div class="text-[10px] font-bold uppercase tracking-widest text-emerald-500">Out <span class="normal-case font-normal opacity-70">api → client</span></div>
                          <label class="flex items-center gap-1 text-[10px] text-gray-500 cursor-pointer">
                            <input type="checkbox" [checked]="panelAccess()!.all_fields_out"
                                   (change)="updateAllFields('out', !panelAccess()!.all_fields_out)"
                                   class="rounded border-gray-300 text-emerald-600 w-3 h-3">
                            all
                          </label>
                        </div>
                        <div class="space-y-1">
                          @for (f of panelInfo()!.fields; track f) {{
                            <label class="flex items-center gap-2 text-xs cursor-pointer">
                              <input type="checkbox"
                                     [checked]="panelAccess()!.all_fields_out || panelAccess()!.out.includes(f)"
                                     [disabled]="panelAccess()!.all_fields_out"
                                     (change)="toggleField(f, 'out', !panelAccess()!.out.includes(f))"
                                     class="rounded border-gray-300 text-emerald-600 w-3 h-3">
                              <span class="font-mono text-gray-700">{{{{ f }}}}</span>
                              @if (panelInfo()!.fields_with_defaults.includes(f)) {{
                                <span class="text-[9px] bg-gray-100 text-gray-400 px-1 rounded" title="Has DB default">auto</span>
                              }}
                            </label>
                          }}
                        </div>
                      </div>

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

  readonly verbs = ['GET', 'POST', 'PUT', 'DELETE'] as const;

  readonly catalogEntries = computed(() => Object.entries(this.catalog()));

  readonly panelAccess = computed<AccessEntry | undefined>(() => {{
    const p = this.panel();
    const role = this.selectedRole();
    if (!p || !role) return undefined;
    return this.catalog()[p.resource]?.access?.[p.verb]?.[role];
  }});

  readonly panelInfo = computed<ResourceInfo | undefined>(() => {{
    const p = this.panel();
    return p ? this.catalog()[p.resource] : undefined;
  }});

  ngOnInit(): void {{
    const token = this.auth.token();
    if (token !== 'admin') {{
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

  verbColor(verb: string): string {{
    return VERB_COLOR[verb] ?? 'text-gray-600';
  }}

  hasConfigIssue(resource: string, verb: string): boolean {{
    const role = this.selectedRole();
    if (!role) return false;
    const acc = this.catalog()[resource]?.access?.[verb]?.[role];
    if (!acc || verb === 'DELETE') return false;
    const noOut = !acc.all_fields_out && acc.out.length === 0;
    const noIn  = !acc.all_fields_in  && acc.in.length  === 0;
    if (verb === 'GET')  return noOut;
    if (verb === 'POST') return noIn;
    if (verb === 'PUT')  return noIn || noOut;
    return false;
  }}

  isPanel(resource: string, verb: string): boolean {{
    const p = this.panel();
    return p?.resource === resource && p?.verb === verb;
  }}

  togglePanel(resource: string, verb: string): void {{
    this.panel.set(this.isPanel(resource, verb) ? null : {{resource, verb}});
  }}

  selectRole(name: string): void {{
    this.panel.set(null);
    this.selectedRole.set(name);
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

  async updateAllFields(dir: 'in' | 'out', value: boolean): Promise<void> {{
    const acc = this.panelAccess();
    if (!acc) return;
    const body = dir === 'in' ? {{all_fields_in: value}} : {{all_fields_out: value}};
    await fetch(`{version_prefix}/ho_admin/access/${{acc.id}}`, {{
      method: 'PUT',
      headers: {{...this._hdrs, 'Content-Type': 'application/json'}},
      body: JSON.stringify(body),
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
}}
"""
