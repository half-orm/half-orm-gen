import { Component, computed, effect, inject, input, signal, untracked, DestroyRef, afterNextRender, ViewChildren, QueryList, ElementRef } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { filter } from 'rxjs';
${router_link_es}import { Router, ActivatedRoute } from '@angular/router';
import { Location } from '@angular/common';
import { SiloRegistry } from '../../../generated/silo-registry.service';
import type { Row } from '../../../generated/resource.silo';
import { AuthService } from '../../../core/auth.service';
import { isValidFilterValue, normalizeFilterValue, matchFilter, fmtCell, cellTitle, parseFiltersFromUrl, encodeFiltersToUrlParams } from '../../../generated/stores/filters';
import type { FieldType } from '../../../generated/stores/filters';
import { PermissionsMatrixComponent } from '../../../generated/permissions-matrix.component';
import { HoTooltipComponent } from '../../../generated/ho-tooltip.component';
${new_items_badge_import}@Component({
  selector: '$selector',
  standalone: true,
  imports: [$imports_str],
  templateUrl: './list.component.html',
  styleUrl: './list.component.css',
})
export class ${iname}ListComponent {
  protected silo   = inject(SiloRegistry).get('$map_key');
  protected auth   = inject(AuthService);
  protected router = inject(Router);
  private route = inject(ActivatedRoute);
  private location = inject(Location);
  protected String = String;  // For template use
  protected Object = Object;  // For template use
  protected matchFilter = matchFilter;  // For template use
  protected fmtCell = fmtCell;  // For template use
  protected cellTitle = cellTitle;  // For template use$pk_id_line
  private destroyRef = inject(DestroyRef);

  @ViewChildren('dataRow') dataRows!: QueryList<ElementRef<HTMLTableRowElement>>;
  private observer?: IntersectionObserver;
  private currentLastElement?: Element;
  private filterDebounceTimer?: number;
  private hadFilters = false;

  readonly filters  = input<Partial<Row>>({});
  readonly embedded = input(false);

  localFilters = signal<Record<string, string>>({});
  showNewOnly  = signal(false);
$field_types_map
$display_items_block

  toggleShowNewOnly(): void {
    this.showNewOnly.update(v => !v);
  }

  constructor() {
    // Initialize filters from URL or store before loading data
    this.initFiltersFromUrl();

    effect(() => {
      const _token = this.auth.token();
      const _v    = this.auth.accessVersion();
      const _rv   = this.auth.resourceAccessVersion()['$map_key'];
      const _sim  = this.auth.simulatedRole();
      this.silo.list(this.filters());
    });

    // Set up observer
    this.observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && this.silo.hasMore() && !this.silo.isLoading()) {
          this.silo.loadMore(this.filters());
        }
      },
      { rootMargin: '0px 0px 400px 0px' }
    );

    // Re-observe when items change (must be in constructor for injection context)
    effect(() => {
      this.silo.items().length;  // Track changes
      untracked(() => {
        setTimeout(() => this.updateObservedElement(), 0);
      });
    });

    // Initial observation after render
    afterNextRender(() => {
      this.updateObservedElement();
    });

    this.destroyRef.onDestroy(() => {
      this.observer?.disconnect();
    });
  }

  private updateObservedElement() {
    if (this.currentLastElement) this.observer?.unobserve(this.currentLastElement);
    const rows = this.dataRows.toArray();
    if (rows.length > 0) {
      const lastElement = rows[rows.length - 1].nativeElement;
      this.currentLastElement = lastElement;
      this.observer?.observe(lastElement);
    }
  }

  sortBy(f: string): void {
    if (this.silo.sortField() === f) this.silo.sortAsc.set(!this.silo.sortAsc());
    else { this.silo.sortField.set(f); this.silo.sortAsc.set(true); }
  }
  setFilter(f: string, v: string): void {
    const updated = { ...this.localFilters(), [f]: v };
    this.localFilters.set(updated);

    // Apply filters on backend with debounce
    if (this.filterDebounceTimer) clearTimeout(this.filterDebounceTimer);
    this.filterDebounceTimer = window.setTimeout(() => {
      // Convert local filters to backend search query (q=col1:val1,col2:val2)
      // Only include valid filters based on field type
      const filterPairs: string[] = [];
      Object.entries(updated).forEach(([key, val]) => {
        if (val && isValidFilterValue(key, val, this.fieldTypes)) {
          const normalizedVal = normalizeFilterValue(key, val, this.fieldTypes);
          filterPairs.push(`$${key}:$${normalizedVal}`);
        }
      });
      const hasFiltersNow = filterPairs.length > 0;

      // Update URL with current filters
      this.syncFiltersToUrl(updated);

      // Only trigger if we have filters now, or we had filters before (to clear them)
      if (hasFiltersNow || this.hadFilters) {
        this.hadFilters = hasFiltersNow;
        // Reset pagination state and clear loaded filters cache
        this.silo.resetFilterState();
        const searchParams = hasFiltersNow ? { q: filterPairs.join(',') } as any : {};
        this.silo.list(searchParams, 0);
      }
    }, 600);
  }
  jsonDialogContent = signal<string | null>(null);
  showJson(v: unknown): void { this.jsonDialogContent.set(JSON.stringify(v, null, 2)); }
  cellClick(e: Event, v: unknown): void {
    if (v != null && typeof v === 'object') { e.stopPropagation(); this.showJson(v); }
  }

  private initFiltersFromUrl(): void {
    if (this.embedded()) return; // Don't sync URL for embedded components

    const params = this.route.snapshot.queryParams;
    if (params['new'] === '1') this.showNewOnly.set(true);
    const urlFilters = parseFiltersFromUrl(params, this.fieldTypes);

    // If URL has filters, use them (priority)
    if (Object.keys(urlFilters).length > 0) {
      this.localFilters.set(urlFilters);
      this.silo.filters.set(urlFilters);
    } else {
      // Otherwise, try to restore from store
      const storeFilters = this.silo.filters();
      if (Object.keys(storeFilters).length > 0) {
        this.localFilters.set(storeFilters);
        // Update URL to reflect store filters
        this.syncFiltersToUrl(storeFilters);
      }
    }
  }

  private syncFiltersToUrl(filters: Record<string, string>): void {
    if (this.embedded()) return; // Don't sync URL for embedded components

    // Update store with current filters
    this.silo.filters.set(filters);

    const queryParams: Record<string, string> = {};

    // Preserve non-filter params
    Object.entries(this.route.snapshot.queryParams).forEach(([key, value]) => {
      if (!key.startsWith('f_') && typeof value === 'string') {
        queryParams[key] = value;
      }
    });

    // Add filter params (using shared function)
    const filterParams = encodeFiltersToUrlParams(filters, this.fieldTypes);
    Object.assign(queryParams, filterParams);

    // Use replaceState to avoid polluting browser history
    const urlTree = this.router.createUrlTree([], {
      relativeTo: this.route,
      queryParams,
      queryParamsHandling: '' // Replace all params
    });

    this.location.replaceState(urlTree.toString());
  }

  clearAllFilters(): void {
    this.localFilters.set({});
    this.syncFiltersToUrl({});
  }

  fkNewQueryParams(): Record<string, string> {
    const fkAuto = this.silo.fkAutoFields('POST');
    const f = this.filters();
    const params: Record<string, string> = {};
    for (const [field, rule] of Object.entries(fkAuto)) {
      if (rule === 'context' && f[field] != null) params[field] = String(f[field]);
    }
    return params;
  }$select_fn$delete_fn
}
