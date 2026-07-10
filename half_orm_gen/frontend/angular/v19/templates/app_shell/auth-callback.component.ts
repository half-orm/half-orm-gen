import { Component, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from '../../core/auth.service';

@Component({
  selector: 'app-auth-callback',
  standalone: true,
  template: `
    <div class="flex flex-col items-center justify-center h-full text-gray-400 text-sm gap-2">
      @if (error()) {
        <p class="text-red-500">{{ error() }}</p>
      } @else {
        <p>Signing you in…</p>
      }
    </div>
  `
})
export class AuthCallbackComponent {
  private auth   = inject(AuthService);
  private router = inject(Router);
  protected error = signal('');

  constructor() {
    // The token travels in the URL fragment, not the query string — a
    // fragment is never sent to the server by the browser (stripped before
    // the HTTP request line is built), so it never lands in an access log,
    // a proxy log, or a Referer header. See ho_api/federation.py's
    // federation_callback, which redirects here with #token=...
    const hash = new URLSearchParams(window.location.hash.replace(/^#/, ''));
    const token = hash.get('token');
    if (!token) {
      this.error.set('Missing token — sign-in did not complete.');
      return;
    }
    this.auth.setToken(token);
    void this.router.navigate(['/'], { replaceUrl: true });
  }
}
