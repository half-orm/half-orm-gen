import { Component, inject, signal } from '@angular/core';
import { Router, ActivatedRoute } from '@angular/router';
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
  private route  = inject(ActivatedRoute);
  protected error = signal('');

  constructor() {
    const token = this.route.snapshot.queryParamMap.get('token');
    if (!token) {
      this.error.set('Missing token — sign-in did not complete.');
      return;
    }
    this.auth.setToken(token);
    void this.router.navigate(['/'], { replaceUrl: true });
  }
}
