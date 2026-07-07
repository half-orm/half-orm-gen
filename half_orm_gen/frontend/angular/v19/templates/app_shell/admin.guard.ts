import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from './auth.service';

export async function adminGuard(): Promise<boolean> {
  const auth  = inject(AuthService);
  const router = inject(Router);
  if (auth.token() && auth.users().length === 0) {
    await auth._fetchUsers();
  }
  if (auth.isAdmin()) return true;
  void router.navigate(['/ho_bo']);
  return false;
}
