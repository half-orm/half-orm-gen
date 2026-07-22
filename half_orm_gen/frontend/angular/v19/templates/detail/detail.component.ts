import { Component, computed, effect, inject, signal, untracked } from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { Location } from '@angular/common';
import { filter, map } from 'rxjs';
import { FormsModule } from '@angular/forms';
import { RouterLink, Router, ActivatedRoute } from '@angular/router';
import { SiloRegistry } from '../../../generated/silo-registry.service';
import type { Row } from '../../../generated/resource.silo';
import { AuthService } from '../../../core/auth.service';
import { PermissionsMatrixComponent } from '../../../generated/permissions-matrix.component';
import { ${iname}FieldsComponent } from './fields.component';$fk_fields_imports$rev_list_imports$association_imports

@Component({
  selector: '$selector',
  standalone: true,
  imports: [$all_imports],
  templateUrl: './detail.component.html',
  styleUrl: './detail.component.css',
})
export class ${iname}DetailComponent {
  protected registry = inject(SiloRegistry);
  protected silo     = this.registry.get('$map_key');
  protected auth     = inject(AuthService);
  protected router   = inject(Router);
  protected location = inject(Location);
  private route      = inject(ActivatedRoute);
  protected String = String;  // For template use$pk_id_line

  readonly id   = toSignal(this.route.paramMap.pipe(map(p => p.get('id') ?? '')), { initialValue: this.route.snapshot.params['id'] as string });
  readonly item = computed<Row | null>(() => this.silo.byPk().get(this.id()) ?? null);

  readonly editing = signal(false);
  readonly error   = signal('');
$form_class
$association_signals

  constructor() {
    effect(() => {
      void this.auth.token();
      void this.auth.accessVersion();
      void this.auth.resourceAccessVersion()['$map_key'];
      void this.auth.simulatedRole();
      if (!this.item()) untracked(() => this.silo.get(this.id() as any).subscribe());
    });
    effect(() => {
      if (this.item()) this.silo.markRead(this.id());
    });$form_effect$ws_effect$fk_fetch_effects$association_effects
  }

  str(v: unknown): string { return String(v); }
  objectEntries(o: Record<string, unknown> | undefined | null): [string, unknown][] { return o ? Object.entries(o) : []; }$handle_update
}
