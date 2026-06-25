/**
 * Testing utilities for generated Angular components.
 *
 * Provides fake implementations of SiloRegistry, AuthService, Router,
 * Location and ActivatedRoute. Import in generated .spec.ts files.
 *
 * Usage:
 *   const ctx = testProviders({ accessMap: { 'public/project': { GET: {}, POST: {} } } });
 *   await TestBed.configureTestingModule({
 *     imports: [MyListComponent],
 *     providers: ctx.providers,
 *   }).compileComponents();
 *   expect(ctx.silo.list).toHaveBeenCalled();
 */
import { signal, WritableSignal } from '@angular/core';
import { UrlTree } from '@angular/router';
import { Subject } from 'rxjs';
import { of } from 'rxjs';

import { SiloRegistry } from './silo-registry.service';
import { AuthService } from '../core/auth.service';
import type { Row } from './resource.silo';

// ---------------------------------------------------------------------------
// ResourceSilo fake
// ---------------------------------------------------------------------------

export interface SiloFake {
  items:            WritableSignal<Row[]>;
  byPk:             WritableSignal<Map<string, Row>>;
  isLoading:        WritableSignal<boolean>;
  hasMore:          WritableSignal<boolean>;
  sortField:        WritableSignal<string | null>;
  sortAsc:          WritableSignal<boolean>;
  selectedId:       WritableSignal<string | null>;
  filters:          WritableSignal<Record<string, string>>;
  list:             jasmine.Spy;
  get:              jasmine.Spy;
  create:           jasmine.Spy;
  update:           jasmine.Spy;
  remove:           jasmine.Spy;
  setItem:          jasmine.Spy;
  removeItem:       jasmine.Spy;
  loadMore:         jasmine.Spy;
  resetFilterState: jasmine.Spy;
  getUrl:           jasmine.Spy;
}

export function makeSiloFake(initial: Row[] = []): SiloFake {
  const byPkMap = new Map<string, Row>(
    initial.map(item => [String((item as any).id ?? ''), item])
  );
  return {
    items:            signal(initial),
    byPk:             signal(byPkMap),
    isLoading:        signal(false),
    hasMore:          signal(false),
    sortField:        signal(null),
    sortAsc:          signal(true),
    selectedId:       signal(null),
    filters:          signal({}),
    list:             jasmine.createSpy('list'),
    get:              jasmine.createSpy('get').and.returnValue(of(initial[0] ?? null)),
    create:           jasmine.createSpy('create').and.returnValue(of({})),
    update:           jasmine.createSpy('update').and.returnValue(of({})),
    remove:           jasmine.createSpy('remove').and.returnValue(of(null)),
    setItem:          jasmine.createSpy('setItem'),
    removeItem:       jasmine.createSpy('removeItem'),
    loadMore:         jasmine.createSpy('loadMore'),
    resetFilterState: jasmine.createSpy('resetFilterState'),
    getUrl:           jasmine.createSpy('getUrl').and.returnValue(''),
  };
}

// ---------------------------------------------------------------------------
// SiloRegistry fake
// ---------------------------------------------------------------------------

export type RegistryFake = ReturnType<typeof makeRegistryFake>;

export function makeRegistryFake(silo: SiloFake) {
  return {
    get:    jasmine.createSpy('get').and.returnValue(silo),
    tryGet: jasmine.createSpy('tryGet').and.returnValue(silo),
    meta:   signal({}),
  };
}

// ---------------------------------------------------------------------------
// AuthService fake
// ---------------------------------------------------------------------------

export type AuthFake = ReturnType<typeof makeAuthFake>;

export function makeAuthFake(accessMap: Record<string, any> = {}) {
  return {
    token:         signal('test-token'),
    access:        signal(accessMap),
    wsEvent$:      new Subject<{ event: string; resource: string; id: string }>(),
    fetchedRoutes: new Set<string>(),
  };
}

// ---------------------------------------------------------------------------
// Router + Location fakes
// ---------------------------------------------------------------------------

export function makeRouterFake() {
  return {
    navigate:      jasmine.createSpy('navigate').and.returnValue(Promise.resolve(true)),
    createUrlTree: jasmine.createSpy('createUrlTree').and.returnValue({} as UrlTree),
  };
}

export function makeLocationFake() {
  return {
    back:         jasmine.createSpy('back'),
    replaceState: jasmine.createSpy('replaceState'),
  };
}

// ---------------------------------------------------------------------------
// ActivatedRoute fake
// ---------------------------------------------------------------------------

export function makeRouteFake(
  params:      Record<string, string> = {},
  queryParams: Record<string, string> = {},
) {
  return { snapshot: { params, queryParams } };
}

// ---------------------------------------------------------------------------
// testProviders — one-call setup for TestBed
// ---------------------------------------------------------------------------

import { Router, ActivatedRoute } from '@angular/router';
import { Location } from '@angular/common';

export interface TestContext {
  silo:      SiloFake;
  registry:  RegistryFake;
  auth:      AuthFake;
  router:    ReturnType<typeof makeRouterFake>;
  location:  ReturnType<typeof makeLocationFake>;
  route:     ReturnType<typeof makeRouteFake>;
  providers: { provide: any; useValue: any }[];
}

export function testProviders(opts: {
  initial?:     Row[];
  accessMap?:   Record<string, any>;
  routeParams?: Record<string, string>;
} = {}): TestContext {
  const silo     = makeSiloFake(opts.initial ?? []);
  const registry = makeRegistryFake(silo);
  const auth     = makeAuthFake(opts.accessMap ?? {});
  const router   = makeRouterFake();
  const location = makeLocationFake();
  const route    = makeRouteFake(opts.routeParams ?? {});

  return {
    silo, registry, auth, router, location, route,
    providers: [
      { provide: SiloRegistry,   useValue: registry },
      { provide: AuthService,    useValue: auth     },
      { provide: Router,         useValue: router   },
      { provide: Location,       useValue: location },
      { provide: ActivatedRoute, useValue: route    },
    ],
  };
}
