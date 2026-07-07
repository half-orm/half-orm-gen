import { Component, ChangeDetectorRef, ElementRef, computed, input, OnInit, ViewChild, inject } from '@angular/core';
import { PermissionsFieldsComponent } from './permissions-fields.component';
import { AuthService, CatalogEntry } from '../core/auth.service';
import type { Verb, VerbAccess } from './schema.types';

type RoleVerbAccess = { id: string; out: string[]; in: string[]; inherited_out: string[]; inherited_in: string[]; active_filters: string[] };

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
                    <td class="px-4 py-2 text-center">
                      @if (hasAccess(role, verb)) {
                        <span class="text-green-600 cursor-default select-none"
                              (mouseenter)="onEnter($$event, role, verb)"
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

    <!-- shared popover -->
    <div #tooltip popover="manual"
         style="padding:0;border:none;background:transparent;inset:unset;margin:0;overflow:visible">
      @if (hovered) {
        <div class="bg-white border rounded-lg shadow-xl px-3 py-2.5">
          <div class="text-[10px] font-semibold text-gray-400 uppercase tracking-widest mb-2">
            {{ hovered.role }} · {{ hovered.verb }}
          </div>
          <app-permissions-fields [access]="hoveredAccess()" [verb]="hovered.verb" />
        </div>
      }
    </div>
  `,
})
export class PermissionsMatrixComponent implements OnInit {
  readonly catalogEntry = input<CatalogEntry | null>(null);
  readonly defaultOpen  = input(false);
  @ViewChild('tooltip') private tooltipEl!: ElementRef<HTMLElement>;

  open = false;
  ngOnInit(): void { this.open = this.defaultOpen(); }

  readonly verbs: Verb[] = ['GET', 'POST', 'PUT', 'DELETE'];
  hovered: { role: string; verb: Verb } | null = null;

  readonly auth = inject(AuthService);
  private cdr   = inject(ChangeDetectorRef);

  readonly allRoles = computed<string[]>(() => {
    const entry = this.catalogEntry();
    if (!entry) return [];
    const roles = new Set<string>();
    for (const verbEntry of Object.values(entry.access)) {
      for (const role of Object.keys(verbEntry)) roles.add(role);
    }
    return [...roles].sort();
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

  hoveredAccess(): VerbAccess | undefined {
    if (!this.hovered) return undefined;
    const raw = this.catalogEntry()?.access[this.hovered.verb]?.[this.hovered.role] as RoleVerbAccess | undefined;
    if (!raw) return undefined;
    return {
      in:           raw.in,
      out:          raw.out,
      inherited_in:  raw.inherited_in  ?? [],
      inherited_out: raw.inherited_out ?? [],
    };
  }

  onEnter(event: MouseEvent, role: string, verb: Verb): void {
    if (verb === 'DELETE') return;
    this.hovered = { role, verb };
    this.cdr.detectChanges();
    const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
    const el = this.tooltipEl.nativeElement;
    el.style.left = `$${rect.left + rect.width / 2}px`;
    el.style.top  = `$${rect.top - 8}px`;
    el.style.transform = 'translate(-50%, -100%)';
    el.showPopover();
  }

  onLeave(): void {
    this.tooltipEl.nativeElement.hidePopover();
    this.hovered = null;
  }
}
