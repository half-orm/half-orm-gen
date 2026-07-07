import { Component, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from '../../core/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  template: `
    <div class="flex flex-col items-center justify-center h-full text-sm gap-2">
      @if (auth.token()) {
        <p class="text-gray-500">Signed in as <span class="font-semibold text-gray-700">{{ auth.displayName() }}</span></p>
        <p class="text-gray-400">Select a resource from the sidebar.</p>
      } @else if (auth.hasAdmin() === false) {
        <div class="w-80 bg-white border rounded-lg shadow-sm p-5">
          <p class="text-sm font-semibold text-gray-700 mb-3">Create admin account</p>
          <input (input)="signupName.set($$any($$event).target.value)"
                 [value]="signupName()" placeholder="Name"
                 class="w-full text-sm border rounded px-2 py-1.5 mb-2 focus:outline-none focus:ring-1 focus:ring-blue-400"/>
          <input (input)="signupEmail.set($$any($$event).target.value)"
                 [value]="signupEmail()" placeholder="Email" type="email"
                 class="w-full text-sm border rounded px-2 py-1.5 mb-2 focus:outline-none focus:ring-1 focus:ring-blue-400"/>
          <input (input)="signupPassword.set($$any($$event).target.value)"
                 [value]="signupPassword()" placeholder="Password" type="password"
                 class="w-full text-sm border rounded px-2 py-1.5 mb-2 focus:outline-none focus:ring-1 focus:ring-blue-400"/>
          @if (authError()) {
            <p class="text-xs text-red-500 mb-1">{{ authError() }}</p>
          }
          <button (click)="doSignup()"
                  class="w-full text-sm bg-blue-600 text-white px-2 py-1.5 rounded hover:bg-blue-700 transition-colors">
            Create account
          </button>
        </div>
      } @else {
        <div class="w-full max-w-2xl flex flex-col sm:flex-row gap-6 items-start justify-center px-4">
          @if (auth.localAuthEnabled()) {
            <div class="order-1 w-full sm:w-80 bg-white border rounded-lg shadow-sm p-5">
              @if (!showSignup()) {
                <p class="text-sm font-semibold text-gray-700 mb-3">
                  {{ auth.localPeerName() ? 'Sign in on ' + auth.localPeerName() : 'Sign in' }}
                </p>
                <input (input)="loginEmail.set($$any($$event).target.value)"
                       [value]="loginEmail()" placeholder="Email" type="email"
                       class="w-full text-sm border rounded px-2 py-1.5 mb-2 focus:outline-none focus:ring-1 focus:ring-blue-400"/>
                <input (input)="loginPassword.set($$any($$event).target.value)"
                       [value]="loginPassword()" placeholder="Password" type="password"
                       (keydown.enter)="doLogin()"
                       class="w-full text-sm border rounded px-2 py-1.5 mb-2 focus:outline-none focus:ring-1 focus:ring-blue-400"/>
                @if (authError()) {
                  <p class="text-xs text-red-500 mb-1">{{ authError() }}</p>
                }
                <button (click)="doLogin()"
                        class="w-full text-sm bg-blue-600 text-white px-2 py-1.5 rounded hover:bg-blue-700 transition-colors mb-2">
                  Sign in
                </button>
                <button (click)="showSignup.set(true); authError.set('')"
                        class="w-full text-sm text-blue-500 hover:underline">
                  Create account
                </button>
              } @else {
                <p class="text-sm font-semibold text-gray-700 mb-3">Create account</p>
                <input (input)="signupName.set($$any($$event).target.value)"
                       [value]="signupName()" placeholder="Name"
                       class="w-full text-sm border rounded px-2 py-1.5 mb-2 focus:outline-none focus:ring-1 focus:ring-blue-400"/>
                <input (input)="signupEmail.set($$any($$event).target.value)"
                       [value]="signupEmail()" placeholder="Email" type="email"
                       class="w-full text-sm border rounded px-2 py-1.5 mb-2 focus:outline-none focus:ring-1 focus:ring-blue-400"/>
                <input (input)="signupPassword.set($$any($$event).target.value)"
                       [value]="signupPassword()" placeholder="Password" type="password"
                       class="w-full text-sm border rounded px-2 py-1.5 mb-2 focus:outline-none focus:ring-1 focus:ring-blue-400"/>
                @if (authError()) {
                  <p class="text-xs text-red-500 mb-1">{{ authError() }}</p>
                }
                <button (click)="doSignup()"
                        class="w-full text-sm bg-blue-600 text-white px-2 py-1.5 rounded hover:bg-blue-700 transition-colors mb-2">
                  Create account
                </button>
                <button (click)="showSignup.set(false); authError.set('')"
                        class="w-full text-sm text-gray-400 hover:underline">
                  Back to sign in
                </button>
              }
            </div>
          }
          @if (auth.peers().length > 0) {
            <div class="order-2 w-full sm:w-64 bg-white border rounded-lg shadow-sm p-5">
              <p class="text-sm font-semibold text-gray-700 mb-2">Sign in via</p>
              <div class="space-y-1">
                @for (p of auth.peers(); track p.id) {
                  <a [href]="auth.loginUrlForPeer(p.id)"
                     class="block w-full text-sm text-center border rounded px-2 py-1.5 text-gray-700 hover:bg-gray-50 transition-colors">
                    {{ p.name }}
                  </a>
                }
              </div>
            </div>
          }
        </div>
      }
    </div>
  `
})
export class LoginComponent {
  protected auth   = inject(AuthService);
  private   router = inject(Router);

  showSignup     = signal(false);
  loginEmail     = signal('');
  loginPassword  = signal('');
  signupName     = signal('');
  signupEmail    = signal('');
  signupPassword = signal('');
  authError      = signal('');

  async doLogin(): Promise<void> {
    this.authError.set('');
    try {
      await this.auth.loginWithEmail(this.loginEmail(), this.loginPassword());
      void this.router.navigate(['/ho_bo']);
    } catch (e: any) {
      this.authError.set(e.message ?? 'Login failed');
    }
  }

  async doSignup(): Promise<void> {
    this.authError.set('');
    try {
      await this.auth.signupUser(this.signupName(), this.signupEmail(), this.signupPassword());
      void this.router.navigate(['/ho_bo']);
    } catch (e: any) {
      this.authError.set(e.message ?? 'Signup failed');
    }
  }
}
