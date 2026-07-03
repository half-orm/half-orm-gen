import { computed, signal, Signal } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { catchError, filter, map, of, tap } from 'rxjs';
import { AuthService } from '../core/auth.service';
import { registerClear, registerClearForKey } from '../core/state-registry';
import { ResourceSchema } from './schema.types';
import { makePkExtractor, parseCompositePk, buildListUrl, mergeDynamicRoles } from './silo-shared';
import type { Row } from './silo-shared';
export type { Row };

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
  readonly dynamicRoles = signal<Record<string, { ids: string[]; verbs: string[]; put_in?: string[]; put_out?: string[] }>>({});

  // Per-resource access signals — derived from AuthService at runtime
  readonly canCreate:               Signal<boolean>;
  private _inaccessibleGetFields:   Signal<Set<string>>;
  private _inaccessiblePostFields:  Signal<Set<string>>;
  private _inaccessiblePutFields:   Signal<Set<string>>;
  readonly fkAutoPostFields:        Signal<Record<string, string>>;
  readonly fkAutoPutFields:         Signal<Record<string, string>>;
  readonly searchableFields:        Signal<string[]>;

  private loadedFilters = new Map<string, boolean>();
  private pkExtractor: ((item: Row) => string) | null;
  private pkFields: string[];

  constructor(
    readonly key: string,
    readonly schema: ResourceSchema,
    private baseUrl: string,
    private http: HttpClient,
    private auth: AuthService,
  ) {
    this.pkFields = schema.pk_fields;
    this.pkExtractor = makePkExtractor(schema.pk_fields);

    this.canCreate = computed(() => !!(auth.effectiveAccess() as any)[key]?.POST);
    this.fkAutoPostFields = computed(() =>
      (auth.effectiveAccess() as any)[key]?.POST?.fk_auto ?? {}
    );
    this.fkAutoPutFields = computed(() =>
      (auth.effectiveAccess() as any)[key]?.PUT?.fk_auto ?? {}
    );
    this.searchableFields = computed(() =>
      (auth.effectiveAccess() as any)[key]?.GET?.searchable ?? []
    );
    this._inaccessibleGetFields = computed(() => {
      const allFields = schema.fields.map(f => f.name);
      const getAccess = (auth.effectiveAccess() as any)[key]?.GET;
      if (!getAccess) return new Set<string>(allFields);
      const out: string[] | undefined = getAccess.out;
      if (!out || out.length === 0) return new Set<string>(allFields);
      return new Set(allFields.filter(f => !out.includes(f)));
    });
    this._inaccessiblePostFields = computed(() => {
      const inFields: string[] | undefined = (auth.effectiveAccess() as any)[key]?.POST?.in;
      const fkAuto: Record<string, string> = (auth.effectiveAccess() as any)[key]?.POST?.fk_auto ?? {};
      const autoHidden = new Set(['connected_user', 'context']);
      const allFields = schema.fields.map(f => f.name);
      if (inFields === undefined) return new Set(Object.keys(fkAuto).filter(f => autoHidden.has(fkAuto[f])));
      if (inFields.length === 0) return new Set(allFields);
      return new Set(allFields.filter(f => !inFields.includes(f) || autoHidden.has(fkAuto[f])));
    });
    this._inaccessiblePutFields = computed(() => {
      const allFields = schema.fields.map(f => f.name);
      const fkAuto: Record<string, string> = (auth.effectiveAccess() as any)[key]?.PUT?.fk_auto ?? {};
      const staticIn: string[] | undefined = (auth.effectiveAccess() as any)[key]?.PUT?.in;
      if (staticIn !== undefined) {
        if (staticIn.length === 0) return new Set(allFields);
        return new Set(allFields.filter(f => !staticIn.includes(f) || !!fkAuto[f]));
      }
      for (const rd of Object.values(this.dynamicRoles())) {
        const typedRd = rd as { ids: string[]; verbs: string[]; put_in?: string[]; put_out?: string[] };
        if (typedRd.put_in !== undefined) {
          if (typedRd.put_in.length === 0) return new Set(allFields);
          return new Set(allFields.filter(f => !typedRd.put_in!.includes(f) || !!fkAuto[f]));
        }
      }
      if (Object.keys(fkAuto).length) return new Set(Object.keys(fkAuto));
      return new Set<string>();
    });

    registerClear(() => this.clear());
    registerClearForKey(key, () => this.clear());
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

  canAccess(verb: string, id: string): boolean {
    if (!!(this.auth.effectiveAccess() as any)[this.key]?.[verb]) return true;
    return Object.values(this.dynamicRoles()).some(rd => (rd as any).verbs.includes(verb) && (rd as any).ids.includes(id));
  }

  inaccessibleFields(verb: 'GET' | 'POST' | 'PUT' = 'GET'): Set<string> {
    switch (verb) {
      case 'POST': return this._inaccessiblePostFields();
      case 'PUT':  return this._inaccessiblePutFields();
      default:     return this._inaccessibleGetFields();
    }
  }

  canCreateWithFilters(filters: Record<string, unknown>): boolean {
    if (!this.canCreate()) return false;
    const fkAuto = this.fkAutoPostFields();
    return Object.entries(fkAuto).every(([field, rule]) => rule !== 'context' || !!filters[field]);
  }

  listUrl(params: Row = {}): string {
    return buildListUrl(this.baseUrl, params);
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
    this.http.get<{ data: Row[]; meta: { offset: number; limit: number; has_more: boolean; dynamic_roles?: Record<string, { ids: string[]; verbs: string[]; put_in?: string[]; put_out?: string[] }> } }>(
      url, { headers: this.headers }
    ).pipe(
      catchError(() => of({ data: [], meta: { offset, limit: 100, has_more: false, dynamic_roles: undefined } }))
    ).subscribe(response => {
      if (offset === 0 && !searchQ && Object.keys(params).length === 0) this.setItems(response.data);
      else this.mergeItems(response.data, otherParams);
      this.hasMore.set(response.meta.has_more);
      this.currentOffset.set(offset + response.data.length);
      this.isLoading.set(false);
      this.dynamicRoles.set(response.meta.dynamic_roles ?? {});
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
    // For single-PK resources, use the list endpoint so meta.dynamic_roles is populated
    if (this.pkFields.length === 1) {
      const pk = this.pkFields[0];
      const url = this.listUrl({ [pk]: id });
      return this.http.get<{ data: Row[]; meta: { dynamic_roles?: Record<string, { ids: string[]; verbs: string[]; put_in?: string[]; put_out?: string[] }> } }>(
        url, { headers: this.headers }
      ).pipe(
        tap(resp => {
          if (resp.data[0]) this.setItem(resp.data[0]);
          const incoming = resp.meta?.dynamic_roles ?? {};
          this.dynamicRoles.update(current => mergeDynamicRoles(current, incoming, id));
        }),
        map(resp => resp.data[0] ?? null),
        catchError(() => of(null as Row | null))
      );
    }
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

  private mergeItems(newItems: Row[], filterParams: Row = {}): void {
    if (!this.pkExtractor) {
      this.items.set([...this.items(), ...newItems]);
      return;
    }
    const ex = this.pkExtractor;
    const map = new Map(this.byPk());
    const hasFilter = Object.keys(filterParams).length > 0;
    for (const item of newItems) {
      const enriched = hasFilter ? { ...filterParams, ...(item as object) } as Row : item;
      map.set(ex(enriched), enriched);
    }
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
    return parseCompositePk(id);
  }

  clear(): void {
    this.items.set([]);
    this.byPk.set(new Map());
    this.loadedFilters.clear();
    this.hasMore.set(true);
    this.currentOffset.set(0);
  }
}
