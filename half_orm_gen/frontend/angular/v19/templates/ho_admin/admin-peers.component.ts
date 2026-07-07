import { Component, OnInit, inject, signal, computed } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from '../../core/auth.service';

interface PeerInfo { id: string; name: string; url: string; frontend_url: string | null; jwt_public_key: string | null; trusted: boolean; }
interface SelfPeerInfo {
  id: string; name: string; url: string; frontend_url: string | null;
  algorithm: string; public_key: string | null; export_key: string | null;
  export_key_expires_at: string | null;
}

@Component({
  selector: 'app-admin-peers',
  standalone: true,
  template: `
    <div class="max-w-2xl mx-auto p-6 space-y-6">
      <div class="flex items-center justify-between">
        <h1 class="text-xl font-bold">Peers</h1>
        <button (click)="showNewPeer.set(!showNewPeer())"
                class="text-xs text-blue-600 hover:text-blue-800 font-semibold">+ Register peer</button>
      </div>

      @if (selfPeer(); as sp) {
        <div class="border rounded-lg p-4 bg-gray-50 space-y-1.5">
          <div class="text-[10px] font-semibold text-gray-500 uppercase tracking-wide">This peer</div>
          <div class="text-sm text-gray-700" [title]="sp.name">{{ sp.name || '(HO_PEER_NAME not set)' }}</div>
          <div class="text-xs text-gray-500" [title]="sp.url">{{ sp.url || '(HO_PEER_URL not set)' }}</div>
          @if (sp.export_key) {
            <button (click)="copySelfExportKey()"
                    class="text-xs text-blue-600 hover:text-blue-800 font-semibold border border-blue-200 rounded px-3 py-1 hover:bg-blue-50 transition-colors">
              {{ copiedSelfKey() ? 'Copied!' : 'Copy registration key' }}
            </button>
            <div class="text-[10px] text-gray-400">
              Valid 30 min from copy — send it to the other admin by email, chat, etc.
            </div>
          } @else if (sp.algorithm === 'RS256') {
            <div class="text-xs text-amber-500">Set HO_PEER_NAME and HO_PEER_URL to enable</div>
          } @else {
            <div class="text-xs text-amber-500">HS256 — no federation key (set HO_JWT_ALGORITHM=RS256 to federate)</div>
          }
        </div>
      }

      @if (showNewPeer()) {
        <div class="border rounded-lg p-4">
          <div class="flex items-center justify-between mb-3">
            <h2 class="text-sm font-semibold">Register a peer</h2>
            <button (click)="showNewPeer.set(false)" class="text-gray-400 hover:text-gray-600 leading-none text-lg">✕</button>
          </div>
          <p class="text-sm text-gray-500 mb-3">
            Paste the registration key the other peer's admin sent you (email, chat, …) —
            copied from their own "This peer" card above. It carries that peer's name, URL
            and public key, nothing to type by hand — but it expires 30 minutes after being
            copied, so ask for a fresh one if this fails.
          </p>
          <textarea [value]="newPeerRegistrationKey()" (input)="newPeerRegistrationKey.set($$any($$event.target).value)"
                    placeholder="Paste registration key…" rows="6"
                    class="w-full text-xs border rounded px-3 py-2 font-mono mb-3"></textarea>

          @if (newPeerRegistrationKey().trim() && !decodedPeerCard()) {
            <p class="text-sm text-red-500 mb-3">Doesn't look like a valid registration key.</p>
          } @else if (decodedPeerCard(); as card) {
            <div class="border rounded-lg p-3 mb-3 bg-gray-50 text-sm space-y-1">
              <div class="text-[10px] font-semibold text-gray-400 uppercase tracking-wide mb-1">
                You are about to register
              </div>
              <div><span class="text-gray-400">Name</span> — <span class="font-semibold text-gray-800">{{ card.name }}</span></div>
              <div><span class="text-gray-400">URL</span> — <span class="font-mono text-xs text-gray-700">{{ card.url }}</span></div>
              @if (card.frontend_url) {
                <div><span class="text-gray-400">Frontend</span> — <span class="font-mono text-xs text-gray-700">{{ card.frontend_url }}</span></div>
              }
              <div><span class="text-gray-400">Id</span> — <span class="font-mono text-xs text-gray-700">{{ card.id }}</span></div>
              @if (decodedPeerCardExpired()) {
                <div class="text-red-500 text-xs font-semibold pt-1">⚠ Expired — ask for a fresh key</div>
              }
            </div>
          }

          @if (newPeerError()) {
            <p class="text-sm text-red-500 mb-3">{{ newPeerError() }}</p>
          }
          <button (click)="createPeer()"
                  [disabled]="!decodedPeerCard() || decodedPeerCardExpired()"
                  class="bg-blue-600 text-white text-sm rounded px-4 py-2 hover:bg-blue-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed">
            Register peer
          </button>
        </div>
      }

      <div class="space-y-1.5">
        @for (p of peers(); track p.id) {
          <div class="group relative border rounded px-3 py-2">
            <div class="flex items-center justify-between gap-1">
              <span class="text-sm font-semibold text-gray-700 truncate">{{ p.name }}</span>
              <button (click)="deletePeer(p.id)"
                      class="text-[10px] px-1 rounded opacity-0 group-hover:opacity-100 transition-opacity text-gray-400 hover:text-red-500"
                      title="Remove peer">✕</button>
            </div>
            <div class="text-xs text-gray-400 truncate">{{ p.url }}</div>
            <label class="flex items-center gap-1 mt-1 cursor-pointer select-none">
              <input type="checkbox" [checked]="p.trusted"
                     (change)="togglePeerTrusted(p)"
                     class="rounded border-gray-300" />
              <span class="text-xs" [class]="p.trusted ? 'text-emerald-600' : 'text-gray-400'">
                {{ p.trusted ? 'trusted' : 'untrusted' }}
              </span>
            </label>
          </div>
        } @empty {
          <p class="text-gray-400 text-sm text-center mt-4">No peers registered.</p>
        }
      </div>
    </div>
  `,
})
export class AdminPeersComponent implements OnInit {
  private auth   = inject(AuthService);
  private router = inject(Router);

  readonly peers                  = signal<PeerInfo[]>([]);
  readonly selfPeer               = signal<SelfPeerInfo | null>(null);
  readonly copiedSelfKey          = signal(false);
  readonly showNewPeer            = signal(false);
  readonly newPeerRegistrationKey = signal('');
  readonly newPeerError           = signal('');

  readonly decodedPeerCard = computed<{
    id?: string; name?: string; url?: string; frontend_url?: string; expires_at?: string;
  } | null>(() => {
    const raw = this.newPeerRegistrationKey().trim();
    if (!raw) return null;
    try {
      const card = JSON.parse(atob(raw));
      return (card && typeof card === 'object' && card.id && card.name && card.url) ? card : null;
    } catch {
      return null;
    }
  });

  readonly decodedPeerCardExpired = computed<boolean>(() => {
    const expiresAt = this.decodedPeerCard()?.expires_at;
    return !!expiresAt && new Date(expiresAt).getTime() < Date.now();
  });

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
    const [peersRes, selfPeerRes] = await Promise.all([
      fetch('$version_prefix/ho_admin/peer', { headers: this._hdrs }),
      fetch('$version_prefix/ho_admin/peer/self', { headers: this._hdrs }),
    ]);
    if (peersRes.ok) this.peers.set(await peersRes.json() as PeerInfo[]);
    if (selfPeerRes.ok) this.selfPeer.set(await selfPeerRes.json() as SelfPeerInfo);
  }

  private async _loadPeers(): Promise<void> {
    const res = await fetch('$version_prefix/ho_admin/peer', { headers: this._hdrs });
    if (res.ok) this.peers.set(await res.json() as PeerInfo[]);
  }

  async copySelfExportKey(): Promise<void> {
    // Refetch right before copying — export_key's expiry starts from when
    // it was generated, not when it's copied, so a card loaded long ago
    // (tab left open) would otherwise already be burning down its 30 min.
    const res = await fetch('$version_prefix/ho_admin/peer/self', { headers: this._hdrs });
    if (res.ok) this.selfPeer.set(await res.json() as SelfPeerInfo);
    const key = this.selfPeer()?.export_key;
    if (!key) return;
    await navigator.clipboard.writeText(key);
    this.copiedSelfKey.set(true);
    setTimeout(() => this.copiedSelfKey.set(false), 1500);
  }

  async createPeer(): Promise<void> {
    const registration_key = this.newPeerRegistrationKey().trim();
    if (!registration_key) return;
    this.newPeerError.set('');
    const res = await fetch('$version_prefix/ho_admin/peer', {
      method: 'POST',
      headers: { ...this._hdrs, 'Content-Type': 'application/json' },
      body: JSON.stringify({ registration_key }),
    });
    if (!res.ok) {
      this.newPeerError.set(((await res.json()) as any).detail ?? 'Registration failed');
      return;
    }
    this.newPeerRegistrationKey.set('');
    this.showNewPeer.set(false);
    await this._loadPeers();
  }

  async togglePeerTrusted(peer: PeerInfo): Promise<void> {
    await fetch(`$version_prefix/ho_admin/peer/$${peer.id}`, {
      method: 'PUT',
      headers: { ...this._hdrs, 'Content-Type': 'application/json' },
      body: JSON.stringify({ trusted: !peer.trusted }),
    });
    await this._loadPeers();
  }

  async deletePeer(id: string): Promise<void> {
    if (!confirm('Remove this peer? Sign-in delegated from it will stop working.')) return;
    await fetch(`$version_prefix/ho_admin/peer/$${id}`, {
      method: 'DELETE', headers: this._hdrs,
    });
    await this._loadPeers();
  }
}
