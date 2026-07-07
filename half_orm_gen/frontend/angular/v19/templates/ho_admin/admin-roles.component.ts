import { Component, OnInit, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from '../../core/auth.service';

interface RoleInfo { name: string; deletable: boolean; kind: 'system' | 'dynamic' | 'user'; parent_name: string | null; }

@Component({
  selector: 'app-admin-roles',
  standalone: true,
  template: `
    <div class="max-w-md mx-auto p-6">
      <div class="flex items-center justify-between mb-4">
        <h1 class="text-xl font-bold">Roles</h1>
        <button (click)="showNewRole.set(!showNewRole())"
                class="text-xs text-blue-600 hover:text-blue-800 font-semibold">+ New role</button>
      </div>
      @if (showNewRole()) {
        <div class="border rounded-lg p-3 mb-4 bg-gray-50 space-y-1.5">
          <input [value]="newRoleName()" (input)="newRoleName.set($$any($$event.target).value)"
                 placeholder="Role name" class="w-full text-sm border rounded px-2 py-1" />
          <select [value]="newRoleParent()" (change)="newRoleParent.set($$any($$event.target).value)"
                  class="w-full text-sm border rounded px-2 py-1">
            @for (r of roles(); track r.name) {
              <option [value]="r.name">{{ r.name }}</option>
            }
          </select>
          <button (click)="createRole()"
                  class="w-full text-sm bg-blue-600 text-white rounded py-1 hover:bg-blue-700">Create</button>
        </div>
      }
      <div class="space-y-1">
        @for (r of roles(); track r.name) {
          <div class="group relative border rounded px-3 py-2 flex items-center justify-between">
            <div>
              <span class="text-sm font-semibold text-gray-700">{{ r.name }}</span>
              @if (r.kind === 'system') {
                <span class="ml-1.5 text-[10px] px-1.5 rounded bg-gray-100 text-gray-500">sys</span>
              } @else if (r.kind === 'dynamic') {
                <span class="ml-1.5 text-[10px] px-1.5 rounded bg-purple-100 text-purple-600">dyn</span>
              }
              @if (r.parent_name) {
                <div class="text-[10px] text-gray-400 mt-0.5">↳ {{ r.parent_name }}</div>
              }
            </div>
            @if (r.deletable) {
              <button (click)="deleteRole(r.name)"
                      class="text-[10px] px-1 rounded opacity-0 group-hover:opacity-100 transition-opacity text-gray-400 hover:text-red-500"
                      title="Delete role">✕</button>
            }
          </div>
        } @empty {
          <p class="text-gray-400 text-sm text-center mt-4">Loading…</p>
        }
      </div>
    </div>
  `,
})
export class AdminRolesComponent implements OnInit {
  private auth   = inject(AuthService);
  private router = inject(Router);

  readonly roles         = signal<RoleInfo[]>([]);
  readonly showNewRole   = signal(false);
  readonly newRoleName   = signal('');
  readonly newRoleParent = signal('connected');

  private get _hdrs(): Record<string, string> {
    const t = this.auth.token();
    return t ? { Authorization: `Bearer $${t}` } : {};
  }

  async ngOnInit(): Promise<void> {
    if (this.auth.token() && this.auth.users().length === 0) {
      await this.auth._fetchUsers();
    }
    if (!this.auth.isAdmin()) {
      void this.router.navigate(['/ho_bo']);
      return;
    }
    await this._loadRoles();
  }

  private async _loadRoles(): Promise<void> {
    const res = await fetch('$version_prefix/ho_admin/roles', { headers: this._hdrs });
    if (res.ok) this.roles.set(await res.json() as RoleInfo[]);
  }

  async createRole(): Promise<void> {
    const name = this.newRoleName().trim();
    if (!name) return;
    await fetch('$version_prefix/ho_admin/roles', {
      method: 'POST',
      headers: { ...this._hdrs, 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, parent_name: this.newRoleParent() }),
    });
    this.newRoleName.set('');
    this.showNewRole.set(false);
    await this._loadRoles();
  }

  async deleteRole(name: string): Promise<void> {
    if (!confirm(`Delete role "$${name}"?`)) return;
    await fetch(`$version_prefix/ho_admin/roles/$${name}`, {
      method: 'DELETE', headers: this._hdrs,
    });
    await this._loadRoles();
  }
}
