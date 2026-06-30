import { auth } from '$lib/auth.svelte.ts';
import { ResourceSilo } from './resource.silo.svelte.ts';
import type { HoMeta } from './schema.types';

class SiloRegistry {
  meta  = $state<HoMeta>({});
  private silos  = new Map<string, ResourceSilo>();
  private _ready = false;

  async init(apiBase: string): Promise<void> {
    if (this._ready) return;
    const hdrs = auth.token ? { Authorization: `Bearer ${auth.token}` } : {};
    const res = await fetch(`${apiBase}/ho_meta`, { headers: hdrs });
    if (!res.ok) return;
    const m = await res.json() as HoMeta;
    this.meta = m;
    for (const [key, schema] of Object.entries(m)) {
      if (!this.silos.has(key)) {
        this.silos.set(key, new ResourceSilo(key, schema, `${apiBase}/${key}`));
      }
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

export const registry = new SiloRegistry();
