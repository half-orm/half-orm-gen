import { computed, signal, Signal } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { catchError, filter, map, of, tap } from 'rxjs';
import { AuthService } from '../core/auth.service';
import { registerClear } from '../core/state-registry';
import { ResourceSchema } from './schema.types';
import type { PermMatrix } from './schema.types';

export type Row = Record<string, unknown>;

export class ResourceSilo {
  readonly items         = signal<Row[]>([]);
  readonly byPk          = signal(new Map<string, Row>());
  readonly isLoading     = signal(false);
  readonly hasMore       = signal(true);
  readonly currentOffset = signal(0);

  readonly filters    = signal<Record<string, string>>({});
  readonly selectedId = signal<string | null>(null);
  readonly sortField  = signal<string | null>(null);
  readonly sortAsc    = signal(true);

  // Per-resource access signals — derived from AuthService at runtime
  readonly canCreate:             Signal<boolean>;
  readonly canDelete:             Signal<boolean>;
  readonly canEdit:               Signal<boolean>;
  readonly inaccessibleFields:    Signal<Set<string>>;
  readonly inaccessiblePostFields: Signal<Set<string>>;
  readonly inaccessiblePutFields:  Signal<Set<string>>;

  // Static permissions from CRUD_ACCESS (all roles)
  readonly permRoles: string[];
  readonly permMatrix: PermMatrix;

  private loadedFilters = new Map<string, boolean>();
  private pkExtractor: ((item: Row) => string) | null;
  private pkFields: string[];

  constructor(
    readonly key: string,
    readonly schema: ResourceSchema,
    private baseUrl: string,
    private http: HttpClient,
    private auth: AuthService,
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

    this.canCreate = computed(() => !!(auth.access() as any)[key]?.POST);
    this.canDelete = computed(() => !!(auth.access() as any)[key]?.DELETE);
    this.canEdit   = computed(() => !!(auth.access() as any)[key]?.PUT);
    this.inaccessibleFields = computed(() => {
      const out: string[] | undefined = (auth.access() as any)[key]?.GET?.out;
      if (!out || out.length === 0) return new Set<string>();
      const allFields = schema.fields.map(f => f.name);
      return new Set(allFields.filter(f => !out.includes(f)));
    });
    this.inaccessiblePostFields = computed(() => {
      const inFields: string[] | undefined = (auth.access() as any)[key]?.POST?.in;
      const allFields = schema.fields.map(f => f.name);
      if (inFields === undefined) return new Set<string>();
      if (inFields.length === 0) return new Set(allFields);
      return new Set(allFields.filter(f => !inFields.includes(f)));
    });
    this.inaccessiblePutFields = computed(() => {
      const inFields: string[] | undefined = (auth.access() as any)[key]?.PUT?.in;
      const allFields = schema.fields.map(f => f.name);
      if (inFields === undefined) return new Set<string>();
      if (inFields.length === 0) return new Set(allFields);
      return new Set(allFields.filter(f => !inFields.includes(f)));
    });

    registerClear(() => this.clear());
    auth.wsEvent$
      .pipe(filter(ev => ev.resource === key))
      .subscribe(ev => {
        if (ev.event === 'delete') this.removeItem(String(ev.id));
        else this.refresh(String(ev.id)).subscribe();
      });
  }

  private get headers(): HttpHeaders {
    const t = this.auth.token();
    return t ? new HttpHeaders({ Authorization: `Bearer ${t}` }) : new HttpHeaders();
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

  list(params: Row = {}, offset = 0): void {
    const filterKey = JSON.stringify(params);
    if (offset === 0 && this.loadedFilters.get(filterKey)) return;
    if (this.isLoading()) return;

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
    if (this.auth.fetchedRoutes.has(url)) return;
    this.auth.fetchedRoutes.add(url);

    this.isLoading.set(true);
    this.http.get<{ data: Row[]; meta: { offset: number; limit: number; has_more: boolean } }>(
      url, { headers: this.headers }
    ).pipe(
      catchError(() => of({ data: [], meta: { offset, limit: 100, has_more: false } }))
    ).subscribe(response => {
      if (offset === 0 && !searchQ && Object.keys(params).length === 0) this.setItems(response.data);
      else this.mergeItems(response.data);
      this.hasMore.set(response.meta.has_more);
      this.currentOffset.set(offset + response.data.length);
      this.isLoading.set(false);
      if (!response.meta.has_more) this.loadedFilters.set(filterKey, true);
    });
  }

  loadMore(params: Row = {}): void {
    if (!this.hasMore() || this.isLoading()) return;
    this.list(params, this.currentOffset());
  }

  resetFilterState(): void {
    this.loadedFilters.clear();
    this.hasMore.set(true);
    this.currentOffset.set(0);
  }

  get(id: string) {
    const cached = this.byPk().get(id);
    if (cached) return of(cached);
    // Composite PK: decode id back to field→value pairs and fetch via list
    if (this.pkFields.length > 1) {
      const params = this.parseCompositeId(id);
      return this.http.get<{ data: Row[] }>(
        this.listUrl(params), { headers: this.headers }
      ).pipe(
        tap(resp => { if (resp.data[0]) this.setItem(resp.data[0]); }),
        map(resp => resp.data[0] ?? null),
        catchError(() => of(null as Row | null))
      );
    }
    return this.refresh(id);
  }

  refresh(id: string) {
    const url = this.getUrl(id);
    this.auth.fetchedRoutes.add(url);
    return this.http.get<Row>(url, { headers: this.headers }).pipe(
      tap(item => this.setItem(item)),
      catchError(() => of(null as Row | null))
    );
  }

  create(data: Row) {
    return this.http.post<Row>(this.baseUrl, data, {
      headers: this.headers.append('Content-Type', 'application/json'),
    });
  }

  update(id: string, data: Row) {
    return this.http.put<Row>(`${this.baseUrl}/${id}`, data, {
      headers: this.headers.append('Content-Type', 'application/json'),
    });
  }

  remove(id: string) {
    return this.http.delete(`${this.baseUrl}/${id}`, { headers: this.headers });
  }

  private setItems(items: Row[]): void {
    this.items.set(items);
    if (this.pkExtractor) {
      const ex = this.pkExtractor;
      this.byPk.set(new Map(items.map(i => [ex(i), i])));
    }
  }

  private mergeItems(newItems: Row[]): void {
    if (!this.pkExtractor) {
      this.items.set([...this.items(), ...newItems]);
      return;
    }
    const ex = this.pkExtractor;
    const map = new Map(this.byPk());
    for (const item of newItems) map.set(ex(item), item);
    this.byPk.set(map);
    this.items.set([...map.values()]);
  }

  setItem(item: Row): void {
    if (!this.pkExtractor) return;
    const ex = this.pkExtractor;
    const id = ex(item);
    const map = new Map(this.byPk());
    map.set(id, item);
    this.byPk.set(map);
    this.items.update((items: Row[]) => {
      const idx = items.findIndex((i: Row) => ex(i) === id);
      if (idx >= 0) { const next = [...items]; next[idx] = item; return next; }
      return [...items, item];
    });
  }

  removeItem(id: string): void {
    if (!this.pkExtractor) return;
    const ex = this.pkExtractor;
    const map = new Map(this.byPk());
    map.delete(id);
    this.byPk.set(map);
    this.items.update((items: Row[]) => items.filter((i: Row) => ex(i) !== id));
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
    this.items.set([]);
    this.byPk.set(new Map());
    this.loadedFilters.clear();
    this.hasMore.set(true);
    this.currentOffset.set(0);
  }
}
