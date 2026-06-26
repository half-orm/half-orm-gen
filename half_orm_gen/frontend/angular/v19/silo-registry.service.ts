import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { AuthService } from '../core/auth.service';
import { HoMeta } from './schema.types';
import { ResourceSilo } from './resource.silo';
import { PERMISSIONS } from './permissions-data';

@Injectable({ providedIn: 'root' })
export class SiloRegistry {
  private http = inject(HttpClient);
  private auth = inject(AuthService);

  readonly meta  = signal<HoMeta>({});
  private silos  = new Map<string, ResourceSilo>();
  private _ready = false;

  async init(apiBase: string): Promise<void> {
    const m = await firstValueFrom(this.http.get<HoMeta>(`${apiBase}/ho_meta`));
    this.meta.set(m);
    this.silos.clear();
    for (const [key, schema] of Object.entries(m)) {
      const perms = PERMISSIONS[key] ?? {};
      this.silos.set(
        key,
        new ResourceSilo(
          key, schema, `${apiBase}/${key}`, this.http, this.auth,
          perms.roles ?? [],
          perms.matrix ?? {},
        )
      );
    }
    this._ready = true;
  }

  get ready(): boolean { return this._ready; }

  get(key: string): ResourceSilo {
    const silo = this.silos.get(key);
    if (!silo) throw new Error(`No silo for key "${key}". Did you call init()?`);
    return silo;
  }

  tryGet(key: string): ResourceSilo | undefined { return this.silos.get(key); }

  keys(): string[] { return [...this.silos.keys()]; }
}
