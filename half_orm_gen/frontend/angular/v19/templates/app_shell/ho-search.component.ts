import { Component, computed, effect, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { RouterLink, Router, ActivatedRoute } from '@angular/router';
import { map } from 'rxjs';
import { SiloRegistry } from '../../generated/silo-registry.service';
import { AuthService } from '../../core/auth.service';
import { formatLabel } from '../../generated/silo-shared';

const API_BASE = '$version_prefix';

@Component({
  selector: 'app-ho-search',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './ho-search.component.html',
})
export class HoSearchComponent {
  protected auth     = inject(AuthService);
  protected router   = inject(Router);
  protected registry = inject(SiloRegistry);
  private route      = inject(ActivatedRoute);

  private readonly q = toSignal(this.route.queryParamMap.pipe(map(p => p.get('q') ?? '')), { initialValue: '' });
  private readonly r = toSignal(this.route.queryParamMap.pipe(map(p => p.get('r') ?? 'all')), { initialValue: 'all' });

  readonly results  = signal<Record<string, any>>({  });
  readonly loading  = signal(false);
  readonly searched = signal(false);

  constructor() {
    effect(() => {
      const q = this.q();
      const r = this.r();
      void this.auth.token();
      void this.auth.accessVersion();
      if (!q.trim()) { this.results.set({  }); this.searched.set(false); return; }
      void this.runSearch(q, r);
    });
  }

  async runSearch(term: string, resource: string): Promise<void> {
    this.loading.set(true);
    const headers: Record<string, string> = {};
    const tok = this.auth.token();
    if (tok) headers['Authorization'] = `Bearer $${tok}`;
    try {
      const resParam = resource && resource !== 'all' ? `&resource=$${encodeURIComponent(resource)}` : '';
      const res = await fetch(`$${API_BASE}/ho_search?q=$${encodeURIComponent(term)}&limit=50$${resParam}`, { headers });
      this.results.set(res.ok ? await res.json() : {  });
    } finally {
      this.loading.set(false);
      this.searched.set(true);
    }
  }

  readonly resultEntries = computed(() =>
    Object.entries(this.results())
      .map(([resource, val]: [string, any]) => ({
        resource,
        data: (val.data ?? []) as Record<string, any>[],
        searchable_fields: (val.searchable_fields ?? []) as string[],
      }))
      .filter(e => e.data.length > 0)
  );

  get searchTerm(): string { return this.q(); }
  get searchResource(): string { return this.r(); }

  goToDetail(resource: string, row: Record<string, any>): void {
    const meta = this.registry.meta()[resource] as any;
    if (!meta) return;
    const pk: string[] = meta.pk_fields ?? [];
    const id = pk.length === 1
      ? String(row[pk[0]])
      : pk.map((f: string) => `$${f}:$${row[f]}`).join('::');
    void this.router.navigate([`/ho_bo/$${resource}/$${id}`]);
  }

  formatResult(row: Record<string, any>, resource: string, fields: string[]): string {
    const labelFields = (this.registry.meta()[resource] as any)?.label_fields ?? [];
    return formatLabel(row, labelFields, fields);
  }
}
