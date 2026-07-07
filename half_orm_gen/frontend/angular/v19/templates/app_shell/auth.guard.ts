import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from './auth.service';

export function authGuard(): boolean {
  const auth   = inject(AuthService);
  const router = inject(Router);
  if (auth.token()) return true;
  void router.navigate(['/login']);
  return false;
}
