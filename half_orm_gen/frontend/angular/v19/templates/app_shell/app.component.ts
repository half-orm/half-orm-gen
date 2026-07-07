import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet, NavigationEnd, Router } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { filter } from 'rxjs';
import { AuthService } from './core/auth.service';
import { SiloRegistry } from './generated/silo-registry.service';
import { formatLabel } from './generated/silo-shared';

const API_BASE = '$version_prefix';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <div class="h-screen flex flex-col bg-gray-50 overflow-hidden" (click)="closeMenu($$event)">
      @if (!isHome()) {
        <header class="shrink-0 bg-white border-b h-11 flex items-center justify-between px-4">
          <span class="font-bold text-gray-800 shrink-0">halfORM Backoffice</span>
          @if (hasGlobalSearch()) {
            <div class="relative flex-1 mx-6 max-w-lg" (click)="$$event.stopPropagation()">
              <div class="flex items-center border rounded text-xs bg-white overflow-hidden focus-within:ring-1 focus-within:ring-blue-300">
                <input [value]="searchTerm()" (input)="onSearchInput($$any($$event).target.value)"
                       (focus)="reopenSearch()"
                       placeholder="Search…"
                       class="flex-1 px-3 py-1.5 outline-none min-w-0"/>
                <select [value]="searchResource()" (change)="searchResource.set($$any($$event).target.value)"
                        class="border-l px-2 py-1.5 bg-gray-50 text-gray-600 text-[11px] outline-none cursor-pointer max-w-[130px]">
                  @if (searchableResources().length > 1) {
                    <option value="all">All</option>
                  }
                  @for (r of searchableResources(); track r.key) {
                    <option [value]="r.key">{{ r.label }}</option>
                  }
                </select>
              </div>
              @if (searchOpen()) {
                <div class="absolute top-full left-0 right-0 mt-1 bg-white border rounded-lg shadow-xl z-50 max-h-96 overflow-y-auto">
                  @if (searchLoading()) {
                    <div class="px-4 py-3 text-xs text-gray-400">Searching…</div>
                  } @else if (searchResultEntries().length === 0) {
                    <div class="px-4 py-3 text-xs text-gray-400">No results</div>
                  } @else {
                    @for (entry of searchResultEntries(); track entry.resource) {
                      <div class="px-3 pt-2 pb-1 border-b last:border-b-0">
                        <span class="text-[10px] font-bold uppercase tracking-wide text-gray-400 mb-1 block">{{ entry.resource.replace('/', '.') }}</span>
                        @for (row of entry.data; track $$index) {
                          <div (click)="goToDetail(entry.resource, row)"
                               class="px-2 py-1.5 rounded hover:bg-blue-50 cursor-pointer text-xs text-gray-700 truncate">
                            {{ formatResult(row, entry.resource, entry.searchable_fields) }}
                          </div>
                        }
                        @if (entry.has_more) {
                          <a [routerLink]="['/ho_bo/search']" [queryParams]="entry.seeAllParams"
                             (click)="closeSearch()"
                             class="block text-[10px] text-blue-500 hover:underline mt-1">more…</a>
                        }
                      </div>
                    }
                  }
                </div>
              }
            </div>
          }
          <div class="flex items-center gap-2 shrink-0">
          @if (auth.token()) {
            <div class="relative shrink-0">
              <button (click)="menuOpen = !menuOpen; $$event.stopPropagation()"
                      class="flex items-center gap-1 text-xs px-3 py-1 rounded-full border transition-colors border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100">
                {{ auth.displayName() }}
                <span class="opacity-60">{{ menuOpen ? '▲' : '▼' }}</span>
              </button>
              @if (menuOpen) {
                <div class="absolute right-0 top-full mt-1 bg-white border rounded-lg shadow-lg z-50 w-64 p-3"
                     (click)="$$event.stopPropagation()">
                  <p class="text-xs text-gray-500 mb-2">Signed in as <strong>{{ auth.displayName() }}</strong></p>
                  <button (click)="logout()"
                          class="w-full text-left px-2 py-1.5 text-xs text-red-500 hover:bg-red-50 rounded transition-colors">
                    Sign out
                  </button>
                </div>
              }
            </div>
          } @else {
            <a routerLink="/login"
               class="flex items-center gap-1 text-xs px-3 py-1 rounded-full border border-gray-300 text-gray-500 hover:bg-gray-50 transition-colors">
              Sign in
            </a>
          }
          @if (totalNewCount() > 0) {
            <div class="relative shrink-0">
              <button (click)="newItemsMenuOpen = !newItemsMenuOpen; $$event.stopPropagation()"
                      class="flex items-center gap-1 text-xs px-3 py-1 rounded bg-blue-600 text-white hover:bg-blue-700 transition-colors">
                🔔 {{ totalNewCount() }}
              </button>
              @if (newItemsMenuOpen) {
                <div class="absolute right-0 top-full mt-1 bg-white border rounded-lg shadow-lg z-50 w-64 p-2"
                     (click)="$$event.stopPropagation()">
                  @for (entry of newItemsEntries(); track entry.resource) {
                    <a [routerLink]="['/ho_bo/' + entry.resource]" [queryParams]="{ new: '1' }"
                       (click)="newItemsMenuOpen = false"
                       class="flex justify-between items-center px-2 py-1.5 rounded hover:bg-blue-50 text-sm text-gray-700">
                      <span>{{ entry.label }}</span>
                      <span class="text-xs bg-blue-600 text-white rounded-full px-1.5 py-0.5">{{ entry.count }}</span>
                    </a>
                  }
                </div>
              }
            </div>
          }
          </div>
        </header>
        <div class="flex flex-1 overflow-hidden">
          <aside class="w-max shrink-0 bg-white border-r flex flex-col">
            @if (auth.peers().length > 0) {
              <div class="border-b shrink-0">
                <button (click)="showFederationNav = !showFederationNav"
                        class="w-full flex items-center justify-between gap-4 px-3 py-2 text-xs font-semibold text-gray-400 uppercase tracking-wide hover:bg-gray-50 transition-colors">
                  Federation
                  <span class="opacity-60">{{ showFederationNav ? '▲' : '▼' }}</span>
                </button>
                @if (showFederationNav) {
                  <div class="px-2 pb-2 space-y-0.5">
                    @for (p of auth.peers(); track p.id) {
                      <a [href]="auth.federationNavUrl(p)"
                         class="block px-3 py-1.5 rounded hover:bg-gray-100 text-sm text-gray-700 truncate">
                        {{ p.name }}
                      </a>
                    }
                  </div>
                }
              </div>
            }
            <div class="flex flex-col flex-1 overflow-hidden">
              <button (click)="showLocalNav = !showLocalNav"
                      class="w-full shrink-0 flex items-center justify-between gap-4 px-3 py-2 text-xs font-semibold text-gray-400 uppercase tracking-wide hover:bg-gray-50 transition-colors border-b">
                {{ auth.localPeerName() || 'Resources' }}
                <span class="opacity-60">{{ showLocalNav ? '▲' : '▼' }}</span>
              </button>
              @if (showLocalNav) {
                <div class="px-2 pt-2 pb-1 shrink-0">
                  <input [value]="navFilter()" (input)="navFilter.set($$any($$event).target.value)"
                         placeholder="Filter…"
                         class="w-full text-xs border rounded px-2 py-1 text-gray-700"/>
                </div>
                <nav class="flex-1 overflow-y-auto px-2 py-2 space-y-0.5">
                  @for (item of filteredNav(); track item.href) {
                    <a [routerLink]="item.href" routerLinkActive="bg-gray-100 font-semibold"
                       class="block px-3 py-2 rounded hover:bg-gray-100 text-sm text-gray-700">
                      {{ item.label }}
                    </a>
                  }
                </nav>
              }
            </div>
            <div class="px-4 py-3 border-t flex items-center justify-between">
              @if (auth.isAdmin()) {
                <a routerLink="/ho_bo/admin" routerLinkActive="text-blue-600"
                   class="text-gray-400 hover:text-blue-600 transition-colors text-xs font-medium" title="Admin">⚙</a>
              }
              <a routerLink="/schema" routerLinkActive="text-blue-600"
                 class="text-gray-400 hover:text-blue-600 transition-colors" title="Schema">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="w-6 h-6">
                  <path d="M21 6.375c0 2.692-4.03 4.875-9 4.875S3 9.067 3 6.375 7.03 1.5 12 1.5s9 2.183 9 4.875z" />
                  <path d="M12 12.75c2.685 0 5.19-.586 7.078-1.609a8.283 8.283 0 001.897-1.384c.016.121.025.244.025.368C21 12.817 16.97 15 12 15s-9-2.183-9-4.875c0-.124.009-.247.025-.368a8.285 8.285 0 001.897 1.384C6.809 12.164 9.315 12.75 12 12.75z" />
                  <path d="M12 16.5c2.685 0 5.19-.586 7.078-1.609a8.282 8.282 0 001.897-1.384c.016.121.025.244.025.368 0 2.692-4.03 4.875-9 4.875s-9-2.183-9-4.875c0-.124.009-.247.025-.368a8.284 8.284 0 001.897 1.384C6.809 15.914 9.315 16.5 12 16.5z" />
                </svg>
              </a>
            </div>
          </aside>
          <main class="flex-1 overflow-y-auto p-6">
            @if (auth.simulatedRole()) {
              <div class="mb-4 flex items-center gap-3 px-4 py-2 bg-amber-50 border border-amber-300 rounded-lg text-xs text-amber-800">
                <span>⚠ Simulation mode — viewing as <strong>{{ auth.simulatedRole() }}</strong></span>
                <button (click)="auth.exitSimulation()"
                        class="ml-auto px-2 py-1 bg-amber-200 hover:bg-amber-300 rounded text-amber-900 font-medium transition-colors">
                  Exit simulation
                </button>
              </div>
            }
            <router-outlet />
          </main>
        </div>
      }
      @else {
        <main class="flex-1 overflow-y-auto">
          <router-outlet />
        </main>
      }
    </div>
  `
})
export class AppComponent implements OnInit {
  protected auth     = inject(AuthService);
  protected registry = inject(SiloRegistry);
  private   router   = inject(Router);

  readonly isHome = signal(this.router.url === '/');
  navFilter  = signal('');
  menuOpen   = false;
  newItemsMenuOpen = false;
  showFederationNav = false;
  showLocalNav      = true;

  searchTerm     = signal('');
  searchResource = signal('all');
  searchOpen     = signal(false);
  searchLoading  = signal(false);
  searchResults  = signal<Record<string, any>>({});
  private _searchDebounce: ReturnType<typeof setTimeout> | null = null;

  readonly navItems = computed(() =>
    Object.keys(this.registry.meta())
      .map(key => ({ href: `/ho_bo/$${key}`, label: key.replace('/', '.') }))
      .sort((a, b) => a.label.localeCompare(b.label))
  );

  readonly filteredNav = computed(() => {
    const q = this.navFilter().toLowerCase();
    return q ? this.navItems().filter(i => i.label.toLowerCase().includes(q)) : this.navItems();
  });

  readonly searchableResources = computed(() => {
    const access = this.auth.effectiveAccess() as Record<string, any>;
    return Object.keys(access)
      .filter(key => {
        const srch = access[key]?.GET?.searchable;
        return Array.isArray(srch) && srch.length > 0;
      })
      .map(key => ({ key, label: key.replace('/', '.') }))
      .sort((a, b) => a.label.localeCompare(b.label));
  });

  readonly hasGlobalSearch = computed(() => this.searchableResources().length > 0);

  readonly newItemsEntries = computed(() =>
    Object.entries(this.registry.newItemsByResource())
      .map(([resource, count]) => ({ resource, label: resource.replace('/', '.'), count }))
      .sort((a, b) => b.count - a.count)
  );

  readonly totalNewCount = computed(() =>
    this.newItemsEntries().reduce((sum, e) => sum + e.count, 0)
  );

  readonly searchResultEntries = computed(() =>
    Object.entries(this.searchResults())
      .map(([resource, val]: [string, any]) => ({
        resource,
        data: (val.data ?? []) as Record<string, any>[],
        searchable_fields: (val.searchable_fields ?? []) as string[],
        has_more: val.has_more ?? false,
        seeAllParams: { q: this.searchTerm(), r: resource },
      }))
      .filter(e => e.data.length > 0)
  );

  constructor() {
    this.router.events.pipe(
      filter(e => e instanceof NavigationEnd),
      takeUntilDestroyed(),
    ).subscribe(e => this.isHome.set((e as NavigationEnd).urlAfterRedirects === '/'));
  }

  ngOnInit(): void {
    void this.registry.init(API_BASE);
    void this.auth._fetchAccess();
    void this.auth._fetchRoles();
    void this.auth._fetchUsers();
    void this.auth._fetchSetupStatus();
    void this.auth._fetchPeers();
    this.auth.connectWs();
  }

  logout(): void {
    this.auth.logout();
    this.menuOpen = false;
    void this.router.navigate(['/']);
  }

  closeMenu(e: MouseEvent): void {
    if (this.menuOpen && !(e.target as HTMLElement).closest('.relative')) {
      this.menuOpen = false;
    }
    if (this.newItemsMenuOpen && !(e.target as HTMLElement).closest('.relative')) {
      this.newItemsMenuOpen = false;
    }
    if (this.searchOpen()) this.searchOpen.set(false);
  }

  onSearchInput(val: string): void {
    this.searchTerm.set(val);
    if (this._searchDebounce) clearTimeout(this._searchDebounce);
    if (!val.trim()) { this.searchOpen.set(false); this.searchResults.set({}); return; }
    this._searchDebounce = setTimeout(() => void this.runSearch(), 300);
  }

  async runSearch(): Promise<void> {
    const term = this.searchTerm().trim();
    if (!term) return;
    const res = this.searchResource();
    this.searchLoading.set(true);
    this.searchOpen.set(true);
    const headers: Record<string, string> = {};
    const tok = this.auth.token();
    if (tok) headers['Authorization'] = `Bearer $${tok}`;
    try {
      if (res === 'all') {
        const r = await fetch(`$${API_BASE}/ho_search?q=$${encodeURIComponent(term)}&limit=5`, { headers });
        this.searchResults.set(r.ok ? await r.json() : {});
      } else {
        const srch: string[] = (this.auth.effectiveAccess() as any)[res]?.GET?.searchable ?? [];
        if (!srch.length) { this.searchResults.set({}); return; }
        const q = srch.map((f: string) => `$${f}:$${term}`).join(',');
        const r = await fetch(`$${API_BASE}/$${res}?q=$${encodeURIComponent(q)}&limit=5`, { headers });
        if (r.ok) {
          const json = await r.json();
          this.searchResults.set({ [res]: { data: json.data ?? [], searchable_fields: srch, has_more: json.meta?.has_more ?? false } });
        } else {
          this.searchResults.set({});
        }
      }
    } finally {
      this.searchLoading.set(false);
    }
  }

  goToDetail(resource: string, row: Record<string, any>): void {
    const meta = this.registry.meta()[resource] as any;
    if (!meta) return;
    const pk: string[] = meta.pk_fields ?? [];
    const id = pk.length === 1
      ? String(row[pk[0]])
      : pk.map((f: string) => `$${f}:$${row[f]}`).join('::');
    void this.router.navigate([`/ho_bo/$${resource}/$${id}`]);
    this.searchOpen.set(false);
  }

  formatResult(row: Record<string, any>, resource: string, fields: string[]): string {
    const labelFields = (this.registry.meta()[resource] as any)?.label_fields ?? [];
    return formatLabel(row, labelFields, fields);
  }

  closeSearch(): void {
    this.searchOpen.set(false);
  }

  reopenSearch(): void {
    if (Object.keys(this.searchResults()).length > 0) this.searchOpen.set(true);
  }

}

