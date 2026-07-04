import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { AuthService } from '../core/auth.service';
import { HoMeta } from './schema.types';
import { ResourceSilo } from './resource.silo';
@Injectable({ providedIn: 'root' })
export class SiloRegistry {
  private http = inject(HttpClient);
  private auth = inject(AuthService);
  private apiBase = '';

  readonly meta  = signal<HoMeta>({});
  private silos  = new Map<string, ResourceSilo>();
  private _ready = false;

  constructor() {
    // Schema-level facts (e.g. label_fields) aren't per-role, so they ride the
    // same access_reload broadcast as CRUD_ACCESS changes rather than a new event.
    this.auth.wsEvent$.subscribe(ev => {
      if (ev.event === 'access_reload') void this.refreshMeta();
    });
  }

  async init(apiBase: string): Promise<void> {
    this.apiBase = apiBase;
    const m = await firstValueFrom(this.http.get<HoMeta>(`${apiBase}/ho_meta`));
    this.meta.set(m);
    this.silos.clear();
    for (const [key, schema] of Object.entries(m)) {
      this.silos.set(
        key,
        new ResourceSilo(key, schema, `${apiBase}/${key}`, this.http, this.auth)
      );
    }
    this._ready = true;
  }

  async refreshMeta(): Promise<void> {
    if (!this.apiBase) return;
    const m = await firstValueFrom(this.http.get<HoMeta>(`${this.apiBase}/ho_meta`));
    this.meta.set(m);
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
