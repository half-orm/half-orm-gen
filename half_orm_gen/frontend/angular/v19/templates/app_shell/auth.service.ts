import { Injectable, computed, signal, inject } from '@angular/core';
import { Router } from '@angular/router';
import { Subject } from 'rxjs';
import { clearAllStates, clearStateForKey } from './state-registry';

export interface WsEvent {
  event: 'create' | 'update' | 'delete' | 'access_reload';
  resource: string;
  id: unknown;
}

export interface HoUser {
  id: string;
  name: string;
  is_admin: boolean;
}

export type CatalogEntry = {
  fields: string[];
  pk_fields: string[];
  fields_with_defaults: string[];
  dynamic_roles: string[];
  filters: { id: string; name: string }[];
  access: Record<string, Record<string, { id: string; out: string[]; in: string[]; active_filters: string[] }>>;
};

@Injectable({ providedIn: 'root' })
export class AuthService {
  private router = inject(Router);

  readonly token    = signal<string | null>(
    typeof sessionStorage !== 'undefined' ? sessionStorage.getItem('ho_token') : null
  );
  readonly access               = signal<Record<string, any>>({});
  readonly roles                = signal<string[]>([]);
  readonly users                = signal<HoUser[]>([]);
  readonly hasAdmin             = signal<boolean | null>(null);
  readonly accessVersion        = signal<number>(0);
  readonly resourceAccessVersion = signal<Record<string, number>>({});
  readonly wsEvent$$             = new Subject<WsEvent>();
  readonly fetchedRoutes        = new Set<string>();

  readonly catalog        = signal<Partial<Record<string, CatalogEntry>>>({});
  readonly simulatedRole  = signal<string | null>(null);
  readonly simulatedAccess = signal<Record<string, any> | null>(null);
  readonly effectiveAccess = computed(() => this.simulatedAccess() ?? this.access());

  readonly peers             = signal<{ id: string; name: string; url: string; frontend_url: string | null }[]>([]);
  readonly localAuthEnabled  = signal<boolean>(true);
  readonly localPeerName     = signal<string | null>(null);
  readonly localPeerId       = signal<string | null>(null);

  readonly userId = computed<string | null>(() => {
    const t = this.token();
    if (!t) return null;
    try { return (JSON.parse(atob(t.split('.')[1].replace(/-/g,'+').replace(/_/g,'/'))) as any)['sub'] ?? null; }
    catch { return null; }
  });

  readonly displayName = computed(() => {
    const id = this.userId();
    if (!id) return 'anonymous';
    return this.users().find(u => u.id === id)?.name ?? 'anonymous';
  });

  readonly isAdmin = computed(() => {
    const id = this.userId();
    return !!id && this.users().some(u => u.id === id && u.is_admin);
  });

  readonly userRoles = computed<string[]>(() => {
    const t = this.token();
    if (!t) return [];
    try { return (JSON.parse(atob(t.split('.')[1].replace(/-/g,'+').replace(/_/g,'/'))) as any)['roles'] ?? []; }
    catch { return []; }
  });

  setToken(jwt: string): void {
    sessionStorage.setItem('ho_token', jwt);
    this.token.set(jwt);
    this.fetchedRoutes.clear();
    clearAllStates();
    this.exitSimulation();
    void this._fetchAccess();
    void this._fetchRoles();
    void this._fetchUsers();
  }

  logout(): void {
    sessionStorage.removeItem('ho_token');
    this.token.set(null);
    this.fetchedRoutes.clear();
    clearAllStates();
    this.exitSimulation();
    if (this.router.url.includes('f_')) {
      void this.router.navigate([this.router.url.split('?')[0]], { queryParams: {} });
    }
    void this._fetchAccess();
    void this._fetchRoles();
  }

  async simulateRole(role: string): Promise<void> {
    const hdrs: Record<string, string> = this.token()
      ? { Authorization: `Bearer $${this.token()}` }
      : {};
    try {
      const res = await fetch(`$version_prefix/ho_admin/simulate-access?role=$${encodeURIComponent(role)}`, { headers: hdrs });
      if (res.ok) {
        this.simulatedAccess.set(await res.json());
        this.simulatedRole.set(role);
        this.fetchedRoutes.clear();
        clearAllStates();
      }
    } catch {}
  }

  exitSimulation(): void {
    this.simulatedRole.set(null);
    this.simulatedAccess.set(null);
    this.fetchedRoutes.clear();
    clearAllStates();
  }

  async _refreshSimulation(): Promise<void> {
    const role = this.simulatedRole();
    if (!role) return;
    const hdrs: Record<string, string> = this.token()
      ? { Authorization: `Bearer $${this.token()}` }
      : {};
    try {
      const res = await fetch(`$version_prefix/ho_admin/simulate-access?role=$${encodeURIComponent(role)}`, { headers: hdrs });
      if (res.ok) this.simulatedAccess.set(await res.json());
    } catch {}
  }

  async _fetchCatalog(): Promise<void> {
    const hdrs: Record<string, string> = this.token()
      ? { Authorization: `Bearer $${this.token()}` }
      : {};
    try {
      const res = await fetch('$version_prefix/ho_admin/catalog', { headers: hdrs });
      if (res.ok) this.catalog.set(await res.json());
    } catch {}
  }

  async loginWithEmail(email: string, password: string): Promise<void> {
    const res = await fetch('$version_prefix/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) throw new Error((await res.json() as any).detail ?? 'Login failed');
    this.setToken(((await res.json()) as any).token);
  }

  async signupUser(name: string, email: string, password: string): Promise<void> {
    const res = await fetch('$version_prefix/auth/signup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, password }),
    });
    if (!res.ok) throw new Error((await res.json() as any).detail ?? 'Signup failed');
    this.setToken(((await res.json()) as any).token);
  }

  async _fetchAccess(): Promise<void> {
    const hdrs: Record<string, string> = this.token()
      ? { Authorization: `Bearer $${this.token()}` }
      : {};
    try {
      const res = await fetch('$version_prefix/ho_access', { headers: hdrs });
      this.access.set(res.ok ? await res.json() : {});
    } catch { this.access.set({}); }
  }

  async _fetchRoles(): Promise<void> {
    try {
      const res = await fetch('$version_prefix/ho_roles');
      if (res.ok) this.roles.set(await res.json());
    } catch {}
  }

  async _fetchUsers(): Promise<void> {
    try {
      const res = await fetch('$version_prefix/ho_users');
      if (res.ok) {
        this.users.set(await res.json());
        if (this.isAdmin()) void this._fetchCatalog();
      }
    } catch {}
  }

  async _fetchSetupStatus(): Promise<void> {
    try {
      const res = await fetch('$version_prefix/ho_setup');
      if (res.ok) this.hasAdmin.set(((await res.json()) as any).has_admin);
    } catch {}
  }

  async _fetchPeers(): Promise<void> {
    try {
      const res = await fetch('$version_prefix/auth/peers');
      if (res.ok) {
        const data = await res.json() as {
          peers: { id: string; name: string; url: string; frontend_url: string | null }[];
          local_auth_enabled: boolean; local_name: string | null; local_id: string | null;
        };
        this.peers.set(data.peers ?? []);
        this.localAuthEnabled.set(data.local_auth_enabled ?? true);
        this.localPeerName.set(data.local_name ?? null);
        this.localPeerId.set(data.local_id ?? null);
      }
    } catch {}
  }

  loginUrlForPeer(peerId: string): string {
    const returnTo = `$${window.location.origin}/auth/callback`;
    return `$version_prefix/auth/login?peer=$${encodeURIComponent(peerId)}&return_to=$${encodeURIComponent(returnTo)}`;
  }

  /**
   * Navigate to a trusted peer's own frontend, arriving already signed in
   * when possible — this triggers delegation on the TARGET's own API
   * directly (as if we'd clicked "sign in via <this peer>" on its login
   * page ourselves), using this peer's own id as the identifier the
   * target peer's `peer` table was registered under (never a free-text
   * name — see planning/identite_federee.md section 4bis). Falls back to
   * a plain link if either side lacks what's needed (non-federated peer,
   * or the target never registered a frontend_url).
   */
  federationNavUrl(peer: { url: string; frontend_url: string | null }): string {
    // No frontend_url registered for this peer (e.g. it never set
    // HO_FRONTEND_URL) — no friendly page to land on, best effort is its
    // bare API origin rather than a guaranteed-broken '.../ho_bo' path.
    if (!peer.frontend_url) return peer.url;
    const localId = this.localPeerId();
    if (!localId) return `$${peer.frontend_url}/ho_bo`;
    const returnTo = `$${peer.frontend_url}/auth/callback`;
    return `$${peer.url}/auth/login?peer=$${encodeURIComponent(localId)}&return_to=$${encodeURIComponent(returnTo)}`;
  }

  async _reloadAccess(resource?: string): Promise<void> {
    if (resource) {
      for (const url of [...this.fetchedRoutes]) {
        if (url.includes(`/$${resource}`)) this.fetchedRoutes.delete(url);
      }
      clearStateForKey(resource);
      await this._fetchAccess();
      if (this.isAdmin()) void this._fetchCatalog();
      if (this.simulatedRole()) await this._refreshSimulation();
      this.resourceAccessVersion.update(v => ({ ...v, [resource]: (v[resource] ?? 0) + 1 }));
    } else {
      this.fetchedRoutes.clear();
      clearAllStates();
      await Promise.all([this._fetchAccess(), this._fetchRoles()]);
      if (this.isAdmin()) void this._fetchCatalog();
      if (this.simulatedRole()) await this._refreshSimulation();
      this.accessVersion.update(v => v + 1);
    }
  }

  connectWs(): void {
    const proto = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss' : 'ws';
    const host  = typeof window !== 'undefined' ? window.location.host : 'localhost:8000';
    const ws = new WebSocket(`$${proto}://$${host}$version_prefix/ws`);
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data) as WsEvent;
        if (msg.event === 'access_reload') { void this._reloadAccess((msg as any).resource); }
        this.wsEvent$$.next(msg);
      } catch {}
    };
    ws.onclose = () => { setTimeout(() => this.connectWs(), 2000); };
    ws.onerror  = () => ws.close();
  }
}
