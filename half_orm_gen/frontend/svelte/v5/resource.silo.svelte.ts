import { auth } from '$lib/auth.svelte.ts';
import { registerClear } from '$lib/stateRegistry';
import type { ResourceSchema } from './schema.types';
import type { PermMatrix } from './schema.types';

export type Row = Record<string, unknown>;

export class ResourceSilo {
  items         = $state<Row[]>([]);
  byPk          = $state(new Map<string, Row>());
  isLoading     = $state(false);
  hasMore       = $state(true);
  currentOffset = $state(0);

  filters    = $state<Record<string, string>>({});
  selectedId = $state<string | null>(null);
  sortField  = $state<string | null>(null);
  sortAsc    = $state(true);

  // Static permissions from CRUD_ACCESS (all roles)
  readonly permRoles: string[];
  readonly permMatrix: PermMatrix;

  // Per-resource access signals — derived from auth at runtime
  canCreate          = $derived(!!(auth.access as any)[this.key]?.POST);
  canDelete          = $derived(!!(auth.access as any)[this.key]?.DELETE);
  canEdit            = $derived(!!(auth.access as any)[this.key]?.PUT);
  inaccessibleFields = $derived.by(() => {
    const out = (auth.access as any)[this.key]?.GET?.out;
    if (!out || !Array.isArray(out) || out.length === 0) return new Set<string>();
    const allFields = this.schema.fields.map((f: any) => f.name as string);
    return new Set(allFields.filter(f => !(out as string[]).includes(f)));
  });
  inaccessiblePostFields = $derived.by(() => {
    const inFields = (auth.access as any)[this.key]?.POST?.in as string[] | undefined;
    const allFields = this.schema.fields.map((f: any) => f.name as string);
    if (inFields === undefined) return new Set<string>();
    if (inFields.length === 0) return new Set(allFields);
    return new Set(allFields.filter(f => !inFields.includes(f)));
  });
  inaccessiblePutFields = $derived.by(() => {
    const inFields = (auth.access as any)[this.key]?.PUT?.in as string[] | undefined;
    const allFields = this.schema.fields.map((f: any) => f.name as string);
    if (inFields === undefined) return new Set<string>();
    if (inFields.length === 0) return new Set(allFields);
    return new Set(allFields.filter(f => !inFields.includes(f)));
  });

  private loadedFilters = new Map<string, boolean>();
  private pkExtractor: ((item: Row) => string) | null;
  private pkFields: string[];

  constructor(
    readonly key: string,
    readonly schema: ResourceSchema,
    private baseUrl: string,
    permRoles: string[] = [],
    permMatrix: PermMatrix = {},
  ) {
    this.permRoles  = permRoles;
    this.permMatrix = permMatrix;

    this.pkFields = schema.pk_fields;
    if (schema.pk_fields.length === 1) {
      const pk = schema.pk_fields[0];
      this.pkExtractor = (item) => String(item[pk]);
    } else if (schema.pk_fields.length > 1) {
      const fields = schema.pk_fields;
      this.pkExtractor = (item) => fields.map(f => `${f}:${item[f]}`).join('::');
    } else {
      this.pkExtractor = null;
    }
    registerClear(() => this.clear());
    $effect.root(() => {
      $effect(() => {
        const ev = auth.lastEvent;
        if (!ev || ev.resource !== key) return;
        if (ev.event === 'delete') this.removeItem(String(ev.id));
        else void this.refresh(String(ev.id as string));
      });
    });
  }

  private get hdrs(): Record<string, string> {
    return auth.token ? { Authorization: `Bearer ${auth.token}` } : {};
  }

  pkValue(item: Row): string | null {
    return this.pkExtractor ? this.pkExtractor(item) : null;
  }

  listUrl(params: Row = {}): string {
    const filtered = Object.fromEntries(
      Object.entries(params)
        .filter(([, v]) => v != null && (typeof v !== 'string' || v !== ''))
        .map(([k, v]) => [`ho_col_${k}`, String(v)])
    );
    const qs = new URLSearchParams(filtered).toString();
    return qs ? `${this.baseUrl}?${qs}` : this.baseUrl;
  }

  getUrl(id: string): string { return `${this.baseUrl}/${id}`; }

  async list(params: Row = {}, offset = 0): Promise<void> {
    const filterKey = JSON.stringify(params);
    if (offset === 0 && this.loadedFilters.get(filterKey)) return;
    if (this.isLoading) return;

    const searchQ = params['q'];
    const otherParams = searchQ ? {} : params;
    const baseUrl = this.listUrl(otherParams);
    const sep = baseUrl.includes('?') ? '&' : '?';
    const urlParams = new URLSearchParams();
    if (searchQ) urlParams.set('q', String(searchQ));
    if (offset > 0) urlParams.set('offset', String(offset));
    urlParams.set('limit', '100');
    const qs = urlParams.toString();
    const url = qs ? `${baseUrl}${sep}${qs}` : baseUrl;
    if (auth.fetchedRoutes.has(url)) return;
    auth.fetchedRoutes.add(url);

    this.isLoading = true;
    try {
      const res = await fetch(url, { headers: this.hdrs });
      if (!res.ok) return;
      const { data, meta } = await res.json() as { data: Row[]; meta: { offset: number; limit: number; has_more: boolean } };
      if (offset === 0 && !searchQ && Object.keys(params).length === 0) this._setItems(data);
      else this._mergeItems(data);
      this.hasMore = meta.has_more;
      this.currentOffset = offset + data.length;
      if (!meta.has_more) this.loadedFilters.set(filterKey, true);
    } finally {
      this.isLoading = false;
    }
  }

  loadMore(params: Row = {}): void {
    if (!this.hasMore || this.isLoading) return;
    void this.list(params, this.currentOffset);
  }

  resetFilterState(): void {
    this.loadedFilters.clear();
    this.hasMore = true;
    this.currentOffset = 0;
  }

  async get(id: string): Promise<Row | null> {
    const cached = this.byPk.get(id);
    if (cached) return cached;
    // Composite PK: decode id back to field→value pairs and fetch via list
    if (this.pkFields.length > 1) {
      const params = this.parseCompositeId(id);
      const res = await fetch(this.listUrl(params), { headers: this.hdrs });
      if (!res.ok) return null;
      const { data } = await res.json() as { data: Row[] };
      if (data[0]) this.setItem(data[0]);
      return data[0] ?? null;
    }
    return this.refresh(id);
  }

  async refresh(id: string): Promise<Row | null> {
    const url = this.getUrl(id);
    auth.fetchedRoutes.add(url);
    const res = await fetch(url, { headers: this.hdrs });
    if (!res.ok) return null;
    const item = await res.json() as Row;
    this.setItem(item);
    return item;
  }

  create(data: Row): Promise<Response> {
    return fetch(this.baseUrl, {
      method: 'POST',
      headers: { ...this.hdrs, 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
  }

  update(id: string, data: Row): Promise<Response> {
    return fetch(`${this.baseUrl}/${id}`, {
      method: 'PUT',
      headers: { ...this.hdrs, 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
  }

  remove(id: string): Promise<Response> {
    return fetch(`${this.baseUrl}/${id}`, {
      method: 'DELETE',
      headers: this.hdrs,
    });
  }

  private _setItems(items: Row[]): void {
    this.items = items;
    if (this.pkExtractor) {
      const ex = this.pkExtractor;
      this.byPk = new Map(items.map(i => [ex(i), i]));
    }
  }

  private _mergeItems(newItems: Row[]): void {
    if (!this.pkExtractor) {
      this.items = [...this.items, ...newItems];
      return;
    }
    const ex = this.pkExtractor;
    const map = new Map(this.byPk);
    for (const item of newItems) map.set(ex(item), item);
    this.byPk = map;
    this.items = [...map.values()];
  }

  setItem(item: Row): void {
    if (!this.pkExtractor) return;
    const ex = this.pkExtractor;
    const id = ex(item);
    const map = new Map(this.byPk);
    map.set(id, item);
    this.byPk = map;
    const idx = this.items.findIndex((i: Row) => ex(i) === id);
    if (idx >= 0) { const next = [...this.items]; next[idx] = item; this.items = next; }
    else this.items = [...this.items, item];
  }

  removeItem(id: string): void {
    if (!this.pkExtractor) return;
    const ex = this.pkExtractor;
    const map = new Map(this.byPk);
    map.delete(id);
    this.byPk = map;
    this.items = this.items.filter((i: Row) => ex(i) !== id);
  }

  private parseCompositeId(id: string): Row {
    const params: Row = {};
    for (const part of id.split('::')) {
      const colon = part.indexOf(':');
      if (colon > 0) params[part.slice(0, colon)] = part.slice(colon + 1);
    }
    return params;
  }

  clear(): void {
    this.items = [];
    this.byPk = new Map();
    this.loadedFilters.clear();
    this.hasMore = true;
    this.currentOffset = 0;
  }
}
