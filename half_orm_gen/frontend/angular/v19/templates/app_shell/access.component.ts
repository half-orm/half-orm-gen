import { Component, computed, inject } from '@angular/core';
import { AuthService } from '../../core/auth.service';

const VERB_COLOR: Record<string, string> = {
  GET:    'bg-blue-100 text-blue-700',
  POST:   'bg-green-100 text-green-700',
  PUT:    'bg-yellow-100 text-yellow-700',
  DELETE: 'bg-red-100 text-red-700',
};

@Component({
  selector: 'app-access',
  standalone: true,
  template: `
    <div class="flex h-full gap-6">
      <div class="w-44 shrink-0">
        <h2 class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Roles</h2>
        @if (rolesLoading()) {
          <p class="text-gray-400 text-sm">Loading…</p>
        } @else {
          <div class="space-y-1">
            @for (role of roles(); track role.name) {
              <div class="w-full text-left px-3 py-2 rounded text-sm"
                   [class]="auth.userRoles().includes(role.name)
                     ? 'bg-blue-100 text-blue-700 font-semibold'
                     : 'text-gray-700'">
                {{ role.name }}
              </div>
            }
          </div>
        }
      </div>

      <div class="flex-1 min-w-0">
        <h1 class="text-2xl font-bold mb-6">
          Authorizations
          <span class="text-base font-normal text-gray-500">— {{ activeRole() }}</span>
        </h1>
        @if (accessEntries().length === 0) {
          <p class="text-gray-500 text-sm">No access granted for this role.</p>
        } @else {
          <div class="space-y-4">
            @for (entry of accessEntries(); track entry[0]) {
              <div class="bg-white rounded-lg shadow-sm overflow-hidden">
                <div class="px-4 py-2 bg-gray-100 font-semibold text-gray-700 text-sm">
                  {{ entry[0] }}
                </div>
                <div class="divide-y">
                  @for (verb of objectEntries(entry[1]); track verb[0]) {
                    <div class="px-4 py-3 flex gap-4 items-start text-sm">
                      <span class="inline-block px-2 py-0.5 rounded font-mono text-xs font-bold w-16 text-center"
                            [class]="verbColor(verb[0])">
                        {{ verb[0] }}
                      </span>
                      <div class="text-gray-700">
                        @if (verb[0] === 'DELETE') {
                          <span class="text-green-600">allowed</span>
                        } @else if (verb[0] === 'GET') {
                          <span class="text-gray-400">out: </span>{{ asGet(verb[1]).join(', ') }}
                        } @else {
                          <div><span class="text-gray-400">in:  </span>{{ asInOut(verb[1]).in.join(', ') }}</div>
                          <div><span class="text-gray-400">out: </span>{{ asInOut(verb[1]).out.join(', ') }}</div>
                        }
                      </div>
                    </div>
                  }
                </div>
              </div>
            }
          </div>
        }
      </div>
    </div>
  `
})
export class AccessComponent {
  protected auth = inject(AuthService);

  readonly roles         = this.auth.roles;
  readonly rolesLoading  = computed(() => this.auth.roles().length === 0);
  readonly activeRole    = computed(() => this.auth.userRoles()[0] ?? 'anonymous');
  readonly accessEntries = computed(() => Object.entries(this.auth.access()));

  objectEntries(obj: any): [string, any][] { return Object.entries(obj ?? {}); }
  verbColor(verb: string): string { return VERB_COLOR[verb] ?? 'bg-gray-100 text-gray-600'; }
  asGet(v: any): string[]               { return v?.out ?? []; }
  asInOut(v: any): {in: string[]; out: string[]} { return { in: v?.in ?? [], out: v?.out ?? [] }; }
}
