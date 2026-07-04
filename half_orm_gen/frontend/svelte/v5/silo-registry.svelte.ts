import { auth } from '$lib/auth.svelte.ts';
import { ResourceSilo } from './resource.silo.svelte.ts';
import type { HoMeta } from './schema.types';

class SiloRegistry {
  meta  = $state<HoMeta>({});
  private silos  = new Map<string, ResourceSilo>();
  private _ready = false;
  private apiBase = '';

  constructor() {
    // Schema-level facts (e.g. label_fields) aren't per-role, so they ride the
    // same access_reload broadcast as CRUD_ACCESS changes rather than a new event.
    // $effect.root: this class is a module-level singleton, not a component,
    // so it needs its own standalone reactive scope (same pattern ResourceSilo
    // uses for its WS subscription).
    $effect.root(() => {
      $effect(() => {
        if (auth.lastEvent?.event === 'access_reload') void this.refreshMeta();
      });
    });
  }

  async init(apiBase: string): Promise<void> {
    if (this._ready) return;
    this.apiBase = apiBase;
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

  async refreshMeta(): Promise<void> {
    if (!this.apiBase) return;
    const hdrs = auth.token ? { Authorization: `Bearer ${auth.token}` } : {};
    const res = await fetch(`${this.apiBase}/ho_meta`, { headers: hdrs });
    if (!res.ok) return;
    this.meta = await res.json() as HoMeta;
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
