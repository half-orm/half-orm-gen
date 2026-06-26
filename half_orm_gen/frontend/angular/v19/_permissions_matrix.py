from half_orm_gen.backend.crud_routes import _resolved_out, _resolved_in


def _build_perm_data(
    crud_access: dict,
    all_field_names: list,
    api_excluded: list,
) -> tuple[str, str]:
    """Return (roles_ts, matrix_ts) TypeScript literals from CRUD_ACCESS.

    matrix_ts encodes VerbAccess objects: { in?: string[] | null, out?: string[] | null }
    null means "all fields"; absent key means "not applicable" (e.g. no 'in' for GET/DELETE).
    """
    verbs = ('GET', 'POST', 'PUT', 'DELETE')
    all_roles: set[str] = set()
    for verb in verbs:
        all_roles.update(crud_access.get(verb, {}).keys())
    roles_sorted = sorted(all_roles)

    def _fields_ts(field_list) -> str:
        if field_list is None or not isinstance(field_list, (list, tuple, set)):
            return 'null'
        filtered = [f for f in field_list if f not in api_excluded and f in all_field_names]
        return '[' + ', '.join(f"'{f}'" for f in filtered) + ']'

    rows = []
    for role in roles_sorted:
        verb_entries = []
        for v in verbs:
            if role not in crud_access.get(v, {}):
                continue
            parts = []
            if v in ('POST', 'PUT'):
                in_val = _resolved_in(crud_access, v, role)
                parts.append(f'in: {_fields_ts(in_val)}')
            if v != 'DELETE':
                out_val = _resolved_out(crud_access, v, role)
                parts.append(f'out: {_fields_ts(out_val)}')
            verb_str = '{ ' + ', '.join(parts) + ' }' if parts else '{}'
            verb_entries.append(f'{v}: {verb_str}')
        if verb_entries:
            rows.append(f"    '{role}': {{ {', '.join(verb_entries)} }}")

    roles_ts = '[' + ', '.join(f"'{r}'" for r in roles_sorted) + ']'
    matrix_ts = ('{\n' + ',\n'.join(rows) + '\n  }') if rows else '{}'
    return roles_ts, matrix_ts


def _permissions_fields_component_ts() -> str:
    return """\
import { Component, Input } from '@angular/core';
import type { Verb, VerbAccess } from './schema.types';

@Component({
  selector: 'app-permissions-fields',
  standalone: true,
  template: `
    @if (access) {
      <div class="text-xs space-y-2">
        @if (verb === 'POST' || verb === 'PUT') {
          <div>
            <div class="text-[10px] font-bold uppercase tracking-widest text-blue-500 mb-1">in</div>
            @if (access.in == null) {
              <em class="text-gray-400">all fields</em>
            } @else if (access.in!.length === 0) {
              <em class="text-gray-400">none</em>
            } @else {
              <div class="flex flex-wrap gap-1 max-w-[200px]">
                @for (f of access.in!; track f) {
                  <span class="bg-blue-50 text-blue-700 border border-blue-200 px-1.5 py-0.5 rounded font-mono text-[10px]">{{ f }}</span>
                }
              </div>
            }
          </div>
        }
        <div>
          <div class="text-[10px] font-bold uppercase tracking-widest text-emerald-500 mb-1">out</div>
          @if (access.out == null) {
            <em class="text-gray-400">all fields</em>
          } @else if (access.out!.length === 0) {
            <em class="text-gray-400">none</em>
          } @else {
            <div class="flex flex-wrap gap-1 max-w-[200px]">
              @for (f of access.out!; track f) {
                <span class="bg-emerald-50 text-emerald-700 border border-emerald-200 px-1.5 py-0.5 rounded font-mono text-[10px]">{{ f }}</span>
              }
            </div>
          }
        </div>
      </div>
    }
  `,
})
export class PermissionsFieldsComponent {
  @Input() access?: VerbAccess;
  @Input() verb: Verb = 'GET';
}
"""


def _permissions_matrix_component_ts() -> str:
    return """\
import { Component, ChangeDetectorRef, ElementRef, Input, OnInit, ViewChild, inject } from '@angular/core';
import { PermissionsFieldsComponent } from './permissions-fields.component';
import { AuthService } from '../core/auth.service';
import type { Verb, VerbAccess, PermMatrix } from './schema.types';

@Component({
  selector: 'app-permissions-matrix',
  standalone: true,
  imports: [PermissionsFieldsComponent],
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
              @for (role of roles; track role) {
                <tr class="border-t" [class.bg-gray-100]="auth.activeRoles().includes(role)">
                  <td class="px-4 py-2 font-mono border-r"
                      [class]="auth.activeRoles().includes(role) ? 'font-bold text-gray-900' : 'text-gray-700'">{{ role }}</td>
                  @for (verb of verbs; track verb) {
                    <td class="px-4 py-2 text-center">
                      @if (permissions[role]?.[verb]) {
                        <span class="text-green-600 cursor-default select-none"
                              (mouseenter)="onEnter($event, role, verb)"
                              (mouseleave)="onLeave()">✓</span>
                      } @else {
                        <span class="text-gray-300 select-none">—</span>
                      }
                    </td>
                  }
                </tr>
              }
            </tbody>
          </table>
        </div>
      }
    </div>

    <!-- shared popover — always in DOM so @ViewChild resolves even before first open -->
    <div #tooltip popover="manual"
         style="padding:0;border:none;background:transparent;inset:unset;margin:0;overflow:visible">
      @if (hovered) {
        <div class="bg-white border rounded-lg shadow-xl px-3 py-2.5">
          <div class="text-[10px] font-semibold text-gray-400 uppercase tracking-widest mb-2">
            {{ hovered.role }} · {{ hovered.verb }}
          </div>
          <app-permissions-fields
            [access]="permissions[hovered.role]![hovered.verb]"
            [verb]="hovered.verb" />
        </div>
      }
    </div>
  `,
})
export class PermissionsMatrixComponent implements OnInit {
  @Input() permissions: PermMatrix = {};
  @Input() roles: string[] = [];
  @Input() defaultOpen = false;
  @ViewChild('tooltip') private tooltipEl!: ElementRef<HTMLElement>;

  open = false;

  ngOnInit(): void { this.open = this.defaultOpen; }
  readonly verbs: Verb[] = ['GET', 'POST', 'PUT', 'DELETE'];
  hovered: { role: string; verb: Verb } | null = null;

  readonly auth = inject(AuthService);
  private cdr = inject(ChangeDetectorRef);

  onEnter(event: MouseEvent, role: string, verb: Verb): void {
    if (verb === 'DELETE') return;
    this.hovered = { role, verb };
    // Synchronously update template so popover content is ready before showPopover()
    this.cdr.detectChanges();
    const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
    const el = this.tooltipEl.nativeElement;
    el.style.left = `${rect.left + rect.width / 2}px`;
    el.style.top = `${rect.top - 8}px`;
    el.style.transform = 'translate(-50%, -100%)';
    el.showPopover();
  }

  onLeave(): void {
    this.tooltipEl.nativeElement.hidePopover();
    this.hovered = null;
  }
}
"""
