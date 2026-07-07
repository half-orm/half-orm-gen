import { Component, ChangeDetectorRef, ElementRef, OnInit, computed, input, signal, ViewChild, inject } from '@angular/core';
import { AuthService, CatalogEntry, CatalogAccessEntry, CatalogFkDep } from '../core/auth.service';
import type { Verb } from './schema.types';

const VERB_COLOR: Record<string, string> = {
  GET:    'text-blue-600',
  POST:   'text-green-600',
  PUT:    'text-yellow-600',
  DELETE: 'text-red-500',
};

@Component({
  selector: 'app-permissions-matrix',
  standalone: true,
  imports: [],
  template: `
    <div class="mb-3">
      <button (click)="open = !open"
              class="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1 select-none">
        <span class="font-medium tracking-wide">Permissions</span>
        <span class="text-[10px]">{{ open ? '▲' : '▼' }}</span>
      </button>
      @if (open) {
        <div class="mt-2 border rounded-lg bg-white inline-block shadow-sm">
          <table class="text-xs">
            <thead>
              <tr class="border-b bg-gray-50">
                <th class="px-4 py-2 text-left font-medium text-gray-500 border-r">Role</th>
                @for (verb of verbs; track verb) {
                  <th class="px-4 py-2 text-center font-medium text-gray-500 w-16">{{ verb }}</th>
                }
              </tr>
            </thead>
            <tbody>
              @for (role of allRoles(); track role) {
                <tr class="border-t hover:bg-gray-50 cursor-pointer"
                    [class.bg-blue-50]="auth.simulatedRole() === role"
                    [class.ring-1]="auth.simulatedRole() === role"
                    [class.ring-blue-400]="auth.simulatedRole() === role"
                    (click)="selectRole(role)">
                  <td class="px-4 py-2 font-mono border-r"
                      [class.font-bold]="auth.simulatedRole() === role"
                      [class.text-blue-700]="auth.simulatedRole() === role"
                      [class.text-gray-700]="auth.simulatedRole() !== role">
                    {{ role }}
                    @if (isDynamic(role)) { <span class="ml-1 text-[9px] text-purple-500 font-semibold uppercase">dyn</span> }
                  </td>
                  @for (verb of verbs; track verb) {
                    <td class="px-4 py-2 text-center" (click)="$$event.stopPropagation()">
                      <div class="flex flex-col items-center gap-0.5">
                        <label class="flex items-center gap-1 cursor-pointer select-none">
                          <input type="checkbox" [checked]="hasAccess(role, verb)"
                                 (change)="toggleAccess($$event, role, verb, !hasAccess(role, verb))"
                                 class="rounded border-gray-300 w-3 h-3">
                          @if (hasAccess(role, verb) && hasConfigIssue(role, verb)) {
                            <span class="text-amber-500 text-xs" title="No fields configured — requests will return 403">⚠</span>
                          }
                        </label>
                        @if (hasAccess(role, verb) && verb !== 'DELETE') {
                          <button (click)="openPanel($$event, role, verb)"
                                  class="text-[9px] leading-tight transition-colors"
                                  [class]="isPanel(role, verb)
                                    ? 'text-blue-600 font-semibold'
                                    : 'text-blue-400 hover:text-blue-600 underline'">
                            {{ isPanel(role, verb) ? '▲' : '▼' }}
                          </button>
                        }
                      </div>
                    </td>
                  }
                </tr>
              }
            </tbody>
          </table>
          @if (auth.simulatedRole()) {
            <div class="px-4 py-2 border-t bg-blue-50 flex items-center gap-2 text-xs">
              <span class="text-blue-700">Simulating <strong>{{ auth.simulatedRole() }}</strong></span>
              <button (click)="auth.exitSimulation()"
                      class="ml-auto text-blue-600 hover:text-blue-800 underline">Exit</button>
            </div>
          }
        </div>
      }
    </div>

    <!-- shared popover: click-to-edit field/filter/fk_auto/label panel for the open (role, verb) cell -->
    <div #tooltip popover="manual"
         style="padding:0;border:none;background:transparent;inset:unset;margin:0;overflow:visible">
      @if (panel(); as p) {
        @if (panelAccess(); as acc) {
          <div class="bg-white border rounded-lg shadow-xl px-5 py-4 max-w-2xl max-h-[70vh] overflow-y-auto">
            <div class="flex items-center justify-between mb-4">
              <span class="text-xs font-semibold text-gray-500">
                <span [class]="verbColor(p.verb)">{{ p.verb }}</span>
                — {{ p.role }} — field access
              </span>
              <button (click)="closePanel()"
                      class="text-gray-400 hover:text-gray-600 leading-none text-base">✕</button>
            </div>

            <div class="flex gap-8 flex-wrap items-start">

              <!-- In fields (POST / PUT) -->
              @if (p.verb === 'POST' || p.verb === 'PUT') {
                <div class="min-w-[140px]">
                  <div class="flex items-center gap-3 mb-2">
                    <div class="text-[10px] font-bold uppercase tracking-widest text-blue-500">In <span class="normal-case font-normal opacity-70">client → api</span></div>
                    <button (click)="addAllFields('in')"
                            class="text-[10px] px-1.5 py-0.5 rounded border border-blue-200 text-blue-500 hover:bg-blue-50">all</button>
                  </div>
                  <div class="space-y-1">
                    @for (f of catalogEntry()!.fields; track f) {
                      @let isInh = acc.inherited_in.includes(f) && !acc.in.includes(f);
                      <label class="flex items-center gap-2 text-xs" [class]="isInh ? 'cursor-default' : 'cursor-pointer'">
                        <input type="checkbox"
                               [checked]="acc.in.includes(f) || isInh"
                               [disabled]="isInh || catalogEntry()!.fields_with_defaults.includes(f)"
                               (change)="!isInh && toggleField(f, 'in', !acc.in.includes(f))"
                               class="rounded border-gray-300 text-blue-600 w-3 h-3">
                        <span class="font-mono"
                              [class]="catalogEntry()!.fields_with_defaults.includes(f) ? 'text-gray-400' : (isInh ? 'text-gray-400 italic' : (acc.fk_auto[f] ? 'text-purple-600' : 'text-gray-700'))">{{ f }}</span>
                        @if (catalogEntry()!.fields_with_defaults.includes(f)) {
                          <span class="text-[9px] bg-gray-100 text-gray-400 px-1 rounded" title="Server-generated — cannot be set in forms">auto</span>
                        } @else if (isInh) {
                          <span class="text-[9px] bg-gray-100 text-gray-400 px-1 rounded italic">inherited</span>
                        } @else if (acc.fk_auto[f]) {
                          <span class="text-[9px] bg-purple-50 text-purple-500 px-1 rounded">{{ acc.fk_auto[f] }}</span>
                        }
                      </label>
                    }
                  </div>
                  @if (fkGroupsInPanel().length > 0) {
                    <div class="mt-3 space-y-2">
                      <div class="text-[9px] font-bold uppercase tracking-widest text-purple-400 mb-1">FK auto-resolve</div>
                      @for (fk of fkGroupsInPanel(); track fk.target) {
                        <div class="border-l-2 border-purple-200 pl-2">
                          <div class="flex items-center gap-2 mb-0.5">
                            <span class="text-[9px] text-purple-500 font-semibold">→ {{ fk.target }}</span>
                            <select class="text-[9px] border rounded px-1 py-0 leading-tight"
                                    [value]="getFkAutoRule(fk.fields)"
                                    (change)="setFkAutoGroup(fk.fields, $$any($$event.target).value)">
                              <option value="">—</option>
                              <option value="connected_user">connected_user</option>
                              <option value="context">context</option>
                              <option value="select">select</option>
                            </select>
                          </div>
                          @for (f of fk.fields; track f) {
                            <span class="text-[9px] font-mono text-purple-400 mr-1">{{ f }}</span>
                          }
                        </div>
                      }
                    </div>
                  }
                </div>
              }

              <!-- Out fields -->
              <div class="min-w-[140px]">
                <div class="flex items-center gap-3 mb-2">
                  <div class="text-[10px] font-bold uppercase tracking-widest text-emerald-500">Out <span class="normal-case font-normal opacity-70">api → client</span></div>
                  <button (click)="addAllFields('out')"
                          class="text-[10px] px-1.5 py-0.5 rounded border border-emerald-200 text-emerald-500 hover:bg-emerald-50">all</button>
                </div>
                <div class="space-y-1">
                  @for (f of catalogEntry()!.fields; track f) {
                    @let isPk = p.verb === 'GET' && catalogEntry()!.pk_fields.includes(f);
                    @let isInh = acc.inherited_out.includes(f) && !acc.out.includes(f);
                    <label class="flex items-center gap-2 text-xs"
                           [class]="(isPk || isInh) ? 'cursor-default' : 'cursor-pointer'">
                      <input type="checkbox"
                             [checked]="isPk || acc.out.includes(f) || isInh"
                             [disabled]="isPk || isInh"
                             (change)="!isPk && !isInh && toggleField(f, 'out', !acc.out.includes(f))"
                             class="rounded border-gray-300 text-emerald-600 w-3 h-3">
                      <span class="font-mono" [class]="isInh ? 'text-gray-400 italic' : 'text-gray-700'">{{ f }}</span>
                      @if (isPk) {
                        <span class="text-[9px] bg-blue-50 text-blue-400 px-1 rounded" title="Primary key — always included in GET">pk</span>
                      } @else if (isInh) {
                        <span class="text-[9px] bg-gray-100 text-gray-400 px-1 rounded italic">inherited</span>
                      } @else if (catalogEntry()!.fields_with_defaults.includes(f)) {
                        <span class="text-[9px] bg-gray-100 text-gray-400 px-1 rounded" title="Has DB default">auto</span>
                      }
                    </label>
                  }
                </div>
              </div>

              <!-- Searchable fields (GET only) -->
              @if (p.verb === 'GET') {
                <div class="min-w-[140px]">
                  <div class="text-[10px] font-bold uppercase tracking-widest text-teal-500 mb-2">Searchable</div>
                  <div class="space-y-1">
                    @for (f of catalogEntry()!.fields; track f) {
                      @if (!catalogEntry()!.pk_fields.includes(f) && (acc.out.includes(f) || acc.inherited_out.includes(f))) {
                        <label class="flex items-center gap-2 text-xs cursor-pointer">
                          <input type="checkbox"
                                 [checked]="acc.searchable.includes(f)"
                                 (change)="toggleSearchable(f, !acc.searchable.includes(f))"
                                 class="rounded border-gray-300 text-teal-600 w-3 h-3">
                          <span class="font-mono text-gray-700">{{ f }}</span>
                        </label>
                      }
                    }
                  </div>
                </div>
              }

              <!-- Filters (GET only) -->
              @if (p.verb === 'GET' && catalogEntry()!.filters.length > 0) {
                <div class="min-w-[140px]">
                  <div class="text-[10px] font-bold uppercase tracking-widest text-violet-500 mb-2">Filters</div>
                  <div class="space-y-1">
                    @for (fi of catalogEntry()!.filters; track fi.id) {
                      <label class="flex items-center gap-2 text-xs cursor-pointer">
                        <input type="checkbox"
                               [checked]="acc.active_filters.includes(fi.id)"
                               (change)="toggleFilter(fi.id, !acc.active_filters.includes(fi.id))"
                               class="rounded border-gray-300 text-violet-600 w-3 h-3">
                        <span class="font-mono text-gray-700">{{ fi.name }}</span>
                      </label>
                    }
                  </div>
                </div>
              }

              <!-- Label fields: resource-level, not per-role — shown once in the GET panel -->
              @if (p.verb === 'GET') {
                <div class="min-w-[180px]">
                  <div class="text-[10px] font-bold uppercase tracking-widest text-teal-500 mb-2">
                    Label fields
                  </div>
                  <div class="text-[9px] text-gray-400 mb-2">
                    Used to display this resource elsewhere (FK select, global search).
                    Not per-role. Auto-marked searchable.
                  </div>
                  <div class="space-y-1">
                    @for (f of catalogEntry()!.fields; track f) {
                      <label class="flex items-center gap-2 text-xs cursor-pointer">
                        <input type="checkbox"
                               [checked]="isLabelField(f)"
                               (change)="toggleLabelField(f, !isLabelField(f))"
                               class="rounded border-gray-300 text-teal-600 w-3 h-3">
                        <span class="font-mono text-gray-700">{{ f }}</span>
                        @if (isLabelField(f)) {
                          <span class="text-teal-500 font-mono">#{{ labelFields().indexOf(f) }}</span>
                        }
                      </label>
                    }
                  </div>
                </div>
              }

            </div>
          </div>
        }
      }
    </div>
  `,
})
export class PermissionsMatrixComponent implements OnInit {
  readonly catalogEntry = input<CatalogEntry | null>(null);
  readonly resource     = input.required<string>();
  readonly defaultOpen  = input(false);
  @ViewChild('tooltip') private tooltipEl!: ElementRef<HTMLElement>;

  open = false;
  ngOnInit(): void { this.open = this.defaultOpen(); }

  readonly verbs: Verb[] = ['GET', 'POST', 'PUT', 'DELETE'];
  panel = signal<{ role: string; verb: Verb } | null>(null);

  readonly auth = inject(AuthService);
  private cdr   = inject(ChangeDetectorRef);

  private get _hdrs(): Record<string, string> {
    const t = this.auth.token();
    return t ? { Authorization: `Bearer $${t}` } : {};
  }

  // Every declared *static* role must always appear as a row — including
  // roles with zero access to this resource yet — so an admin can grant
  // access from scratch, not just toggle roles that already have some
  // grant. A *dynamic* role (schema_name set — see RoleInfo) only makes
  // sense for the one resource it was registered on (e.g. `post_author`
  // for blog.post): offering it as a row on an unrelated resource's matrix
  // would be meaningless, so it's filtered out everywhere else.
  readonly allRoles = computed<string[]>(() => {
    const [schemaName, tableName] = this.resource().split('/');
    return this.auth.roles()
      .filter(r => !r.schema_name || (r.schema_name === schemaName && r.table_name === tableName))
      .map(r => r.name)
      .sort();
  });

  hasAccess(role: string, verb: string): boolean {
    return !!this.catalogEntry()?.access[verb]?.[role];
  }

  isDynamic(role: string): boolean {
    return this.catalogEntry()?.dynamic_roles.includes(role) ?? false;
  }

  selectRole(role: string): void {
    if (this.auth.simulatedRole() === role) this.auth.exitSimulation();
    else void this.auth.simulateRole(role);
  }

  verbColor(verb: string): string {
    return VERB_COLOR[verb] ?? 'text-gray-600';
  }

  getAccess(role: string, verb: string): CatalogAccessEntry | undefined {
    return this.catalogEntry()?.access[verb]?.[role];
  }

  hasConfigIssue(role: string, verb: string): boolean {
    const acc = this.getAccess(role, verb);
    if (!acc || verb === 'DELETE') return false;
    if (verb === 'GET')  return acc.out.length === 0;
    if (verb === 'POST') return acc.in.length  === 0;
    if (verb === 'PUT')  return acc.in.length  === 0 || acc.out.length === 0;
    return false;
  }

  isPanel(role: string, verb: string): boolean {
    const p = this.panel();
    return p?.role === role && p?.verb === verb;
  }

  readonly panelAccess = computed<CatalogAccessEntry | undefined>(() => {
    const p = this.panel();
    if (!p) return undefined;
    const e = this.catalogEntry()?.access[p.verb]?.[p.role];
    return (!e || e._searchable_only) ? undefined : e;
  });

  openPanel(event: MouseEvent, role: string, verb: Verb): void {
    event.stopPropagation();
    if (this.isPanel(role, verb)) {
      this.closePanel();
      return;
    }
    const anchor = event.currentTarget as HTMLElement;
    this.panel.set({ role, verb });
    this._showPanelAt(anchor);
  }

  // Shared by openPanel (fields-toggle button) and toggleAccess (auto-opens
  // the panel right after granting a fresh verb, so its fields can be
  // configured immediately) — both need the popover actually shown and
  // positioned, not just the `panel` signal set. Takes the anchor element
  // itself rather than the triggering Event: `Event.currentTarget` is reset
  // to null once dispatch finishes, so it's unsafe to read after an `await`
  // (toggleAccess awaits a fetch before calling this).
  private _showPanelAt(anchor: HTMLElement): void {
    this.cdr.detectChanges();
    const rect = anchor.getBoundingClientRect();
    const el = this.tooltipEl.nativeElement;
    // Close first if already open for a different cell — showPopover() throws
    // if called while already shown.
    if (el.matches(':popover-open')) el.hidePopover();
    // Show first so offsetWidth/offsetHeight reflect the real (populated) size —
    // a not-yet-shown popover measures 0x0.
    el.showPopover();
    const margin = 8;
    const panelWidth  = el.offsetWidth;
    const panelHeight = el.offsetHeight;
    // Always anchor below the trigger row — flipping above based on measured
    // space proved unreliable in practice. Clamp so it never runs past the
    // bottom of the viewport; max-h-[70vh] + internal scroll on the card
    // covers the rare case where the panel is taller than the viewport.
    const maxTop = window.innerHeight - panelHeight - margin;
    const top = Math.min(rect.bottom + margin, Math.max(maxTop, margin));
    let left = rect.left + rect.width / 2 - panelWidth / 2;
    left = Math.max(margin, Math.min(left, window.innerWidth - panelWidth - margin));
    el.style.left = `$${left}px`;
    el.style.top  = `$${top}px`;
    el.style.transform = 'none';
  }

  closePanel(): void {
    this.tooltipEl.nativeElement.hidePopover();
    this.panel.set(null);
  }

  private get _resourceParts(): [string, string] {
    const [schema_name, table_name] = this.resource().split('/');
    return [schema_name, table_name];
  }

  async toggleAccess(event: Event, role: string, verb: string, enable: boolean): Promise<void> {
    // Captured synchronously: event.currentTarget is nulled out once dispatch
    // finishes, which happens well before the `await fetch(...)` below resolves.
    const anchor = event.currentTarget as HTMLElement;
    const acc = this.getAccess(role, verb);
    if (enable) {
      const [schema_name, table_name] = this._resourceParts;
      await fetch('$version_prefix/ho_admin/access', {
        method: 'POST',
        headers: { ...this._hdrs, 'Content-Type': 'application/json' },
        body: JSON.stringify({ role_name: role, schema_name, table_name, verb }),
      });
      if (verb !== 'DELETE') {
        this.panel.set({ role, verb: verb as Verb });
        this._showPanelAt(anchor);
      }
    } else if (acc) {
      await fetch(`$version_prefix/ho_admin/access/$${acc.id}`, {
        method: 'DELETE', headers: this._hdrs,
      });
      if (this.isPanel(role, verb)) this.closePanel();
    }
  }

  async addAllFields(dir: 'in' | 'out'): Promise<void> {
    const acc  = this.panelAccess();
    const info = this.catalogEntry();
    const p    = this.panel();
    if (!acc || !info || !p) return;
    const existing = dir === 'in' ? acc.in : acc.out;
    const toAdd = info.fields.filter(f =>
      !existing.includes(f) &&
      !(dir === 'in' && info.fields_with_defaults.includes(f)) &&
      !(dir === 'out' && p.verb === 'GET' && info.pk_fields.includes(f))
    );
    if (toAdd.length === 0) return;
    const endpoint = dir === 'in' ? 'field_access_in' : 'field_access_out';
    await fetch(`$version_prefix/ho_admin/$${endpoint}/batch`, {
      method: 'POST',
      headers: { ...this._hdrs, 'Content-Type': 'application/json' },
      body: JSON.stringify({ access_id: acc.id, field_names: toAdd }),
    });
  }

  async toggleField(field: string, dir: 'in' | 'out', add: boolean): Promise<void> {
    const acc = this.panelAccess();
    if (!acc) return;
    const endpoint = dir === 'in' ? 'field_access_in' : 'field_access_out';
    if (add) {
      await fetch(`$version_prefix/ho_admin/$${endpoint}`, {
        method: 'POST',
        headers: { ...this._hdrs, 'Content-Type': 'application/json' },
        body: JSON.stringify({ access_id: acc.id, field_name: field }),
      });
    } else {
      await fetch(`$version_prefix/ho_admin/$${endpoint}/$${acc.id}/$${field}`, {
        method: 'DELETE', headers: this._hdrs,
      });
    }
  }

  async toggleFilter(filterId: string, add: boolean): Promise<void> {
    const acc = this.panelAccess();
    if (!acc) return;
    if (add) {
      await fetch('$version_prefix/ho_admin/access_filter', {
        method: 'POST',
        headers: { ...this._hdrs, 'Content-Type': 'application/json' },
        body: JSON.stringify({ access_id: acc.id, filter_id: filterId }),
      });
    } else {
      await fetch(`$version_prefix/ho_admin/access_filter/$${acc.id}/$${filterId}`, {
        method: 'DELETE', headers: this._hdrs,
      });
    }
  }

  async toggleSearchable(fieldName: string, add: boolean): Promise<void> {
    const acc = this.panelAccess();
    if (!acc) return;
    if (add) {
      await fetch('$version_prefix/ho_admin/field_access_searchable', {
        method: 'POST',
        headers: { ...this._hdrs, 'Content-Type': 'application/json' },
        body: JSON.stringify({ access_id: acc.id, field_name: fieldName, role_name: null }),
      });
    } else {
      await fetch(`$version_prefix/ho_admin/field_access_searchable/$${acc.id}/$${fieldName}`, {
        method: 'DELETE', headers: this._hdrs,
      });
    }
  }

  readonly fkGroupsInPanel = computed<CatalogFkDep[]>(() => {
    const info = this.catalogEntry();
    const acc  = this.panelAccess();
    const p    = this.panel();
    if (!p || !info || !acc || p.verb === 'GET' || p.verb === 'DELETE') return [];
    const inSet = new Set(acc.in);
    return (info.fk_deps ?? []).filter(fk => fk.fields.some(f => inSet.has(f)));
  });

  getFkAutoRule(fields: string[]): string {
    const fkAuto = this.panelAccess()?.fk_auto ?? {};
    return fkAuto[fields[0]] ?? '';
  }

  async setFkAutoGroup(fields: string[], rule: string): Promise<void> {
    const acc = this.panelAccess();
    if (!acc) return;
    for (const field of fields) {
      if (!rule) {
        await fetch(`$version_prefix/ho_admin/field_access_fk_auto/$${acc.id}/$${field}`, {
          method: 'DELETE', headers: this._hdrs,
        });
      } else {
        await fetch('$version_prefix/ho_admin/field_access_fk_auto', {
          method: 'POST',
          headers: { ...this._hdrs, 'Content-Type': 'application/json' },
          body: JSON.stringify({ access_id: acc.id, field_name: field, resolve_rule: rule }),
        });
      }
    }
  }

  readonly labelFields = computed<string[]>(() => this.catalogEntry()?.label_fields ?? []);

  isLabelField(field: string): boolean {
    return this.labelFields().includes(field);
  }

  async toggleLabelField(field: string, add: boolean): Promise<void> {
    const [schema_name, table_name] = this._resourceParts;
    if (add) {
      const label_order = this.labelFields().length;
      await fetch('$version_prefix/ho_admin/field_label', {
        method: 'POST',
        headers: { ...this._hdrs, 'Content-Type': 'application/json' },
        body: JSON.stringify({ schema_name, table_name, field_name: field, label_order }),
      });
    } else {
      await fetch(`$version_prefix/ho_admin/field_label/$${schema_name}/$${table_name}/$${field}`, {
        method: 'DELETE', headers: this._hdrs,
      });
    }
  }
}
