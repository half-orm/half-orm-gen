import { Component, inject, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { AuthService } from '../../core/auth.service';

@Component({
  selector: 'app-auth-delegate',
  standalone: true,
  template: `
    <div class="flex flex-col items-center justify-center h-full text-sm gap-3">
      @if (error()) {
        <p class="text-red-500">{{ error() }}</p>
      }
      @if (redirecting()) {
        <p class="text-gray-400">Already signed in — redirecting…</p>
      } @else {
        <p class="text-gray-500">Sign in to continue to the requesting site.</p>
        <form (submit)="$$event.preventDefault(); submit()" class="flex flex-col gap-2 w-64">
          <input [value]="email()" (input)="email.set($$any($$event.target).value)"
                 type="email" placeholder="Email" class="border rounded px-2 py-1 text-sm" />
          <input [value]="password()" (input)="password.set($$any($$event.target).value)"
                 type="password" placeholder="Password" class="border rounded px-2 py-1 text-sm" />
          <button type="submit" [disabled]="submitting()"
                  class="bg-blue-600 text-white rounded py-1 text-sm hover:bg-blue-700 disabled:opacity-50">
            {{ submitting() ? 'Signing in…' : 'Sign in' }}
          </button>
        </form>
      }
    </div>
  `,
})
export class AuthDelegateComponent {
  private route = inject(ActivatedRoute);
  private auth  = inject(AuthService);
  protected email       = signal('');
  protected password    = signal('');
  protected error       = signal('');
  protected submitting  = signal(false);
  protected redirecting = signal(false);

  private redirectUri = '';
  private csrfState   = '';

  constructor() {
    this.redirectUri = this.route.snapshot.queryParamMap.get('redirect_uri') ?? '';
    this.csrfState   = this.route.snapshot.queryParamMap.get('csrf_state') ?? '';
    if (!this.redirectUri || !this.csrfState) {
      this.error.set('Missing redirect_uri or csrf_state — this page must be reached via a peer login redirect.');
      return;
    }
    // Already signed in on this peer, in this browser tab (sessionStorage) —
    // forward that existing token instead of asking for credentials again.
    // Same trust level as a fresh login: it's the same signed token either
    // way. Not a real cross-tab/cross-device SSO, just a same-tab shortcut —
    // see docs/internals/federation-protocol.md.
    const existing = this.auth.token();
    if (existing) {
      this._redirectWithToken(existing);
    }
  }

  private _redirectWithToken(token: string): void {
    this.redirecting.set(true);
    const sep = this.redirectUri.includes('?') ? '&' : '?';
    window.location.href = `$${this.redirectUri}$${sep}token=$${encodeURIComponent(token)}&csrf_state=$${encodeURIComponent(this.csrfState)}`;
  }

  async submit(): Promise<void> {
    if (!this.redirectUri || !this.csrfState || this.submitting()) return;
    this.submitting.set(true);
    this.error.set('');
    try {
      const res = await fetch('$version_prefix/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: this.email(), password: this.password() }),
      });
      if (!res.ok) {
        this.error.set(((await res.json()) as any).detail ?? 'Login failed');
        return;
      }
      const { token } = (await res.json()) as { token: string };
      this._redirectWithToken(token);
    } finally {
      this.submitting.set(false);
    }
  }
}
