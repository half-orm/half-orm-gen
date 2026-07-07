import { Component, effect, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink, Router, ActivatedRoute } from '@angular/router';
import { SiloRegistry } from '../../../generated/silo-registry.service';
import { formatLabel } from '../../../generated/silo-shared';
import type { Row } from '../../../generated/resource.silo';
import { AuthService } from '../../../core/auth.service';
import { PermissionsMatrixComponent } from '../../../generated/permissions-matrix.component';

@Component({
  selector: '$selector',
  standalone: true,
  imports: [FormsModule, RouterLink, PermissionsMatrixComponent],
  templateUrl: './create.component.html',
  styleUrl: './create.component.css',
})
export class ${iname}CreateComponent {
  protected registry = inject(SiloRegistry);
  protected silo = this.registry.get('$schema_name/$table_name');
  protected auth = inject(AuthService);
  private router = inject(Router);
  private route  = inject(ActivatedRoute);
  private readonly fkTargets: Record<string, string> = {$fk_targets_ts};

  private fkFilterTerms = signal<Record<string, string | undefined>>({});

  fkOptions(targetKey: string): {id: string; label: string}[] {
    const targetSilo = this.registry.tryGet(targetKey);
    if (!targetSilo) return [];
    const labelFields = (this.registry.meta()[targetKey] as any)?.label_fields ?? [];
    const term = (this.fkFilterTerms()[targetKey] ?? '').trim().toLowerCase();
    return targetSilo.items()
      .map(item => ({id: targetSilo.pkValue(item) ?? '', label: formatLabel(item, labelFields)}))
      .filter(opt => opt.id !== '')
      .filter(opt => !term || opt.label.toLowerCase().includes(term));
  }

  private fkFilterTimers: Record<string, ReturnType<typeof setTimeout>> = {};

  onFkFilter(targetKey: string, term: string): void {
    // Instant client-side narrowing of already-loaded options (like the list view's
    // localFilters), independent of the debounced server round-trip below.
    this.fkFilterTerms.update(t => ({ ...t, [targetKey]: term }));

    const targetSilo = this.registry.tryGet(targetKey);
    if (!targetSilo) return;
    if (this.fkFilterTimers[targetKey]) clearTimeout(this.fkFilterTimers[targetKey]);
    this.fkFilterTimers[targetKey] = setTimeout(() => {
      const labelFields = (this.registry.meta()[targetKey] as any)?.label_fields ?? [];
      const trimmed = term.trim();
      targetSilo.resetFilterState();
      const q = trimmed && labelFields.length
        ? labelFields.map((f: string) => `$${f}:*$${trimmed}`).join(',')
        : '';
      targetSilo.list(q ? ({q} as any) : {}, 0);
    }, 300);
  }

  // Custom combobox (not a native <select>): keyed by field name, since several
  // fields could in principle target the same resource.
  fkComboOpen = signal<Record<string, boolean | undefined>>({});
  fkComboText = signal<Record<string, string | undefined>>({});

  openFkCombo(field: string): void {
    this.fkComboOpen.update(o => ({ ...o, [field]: true }));
  }

  closeFkCombo(field: string): void {
    // Delay so a (mousedown) selection on an option registers before blur closes the list.
    setTimeout(() => this.fkComboOpen.update(o => ({ ...o, [field]: false })), 150);
  }

  onFkComboInput(field: string, targetKey: string, term: string): void {
    this.fkComboText.update(t => ({ ...t, [field]: term }));
    (this.form as any)[field] = '';
    this.fkComboOpen.update(o => ({ ...o, [field]: true }));
    this.onFkFilter(targetKey, term);
  }

  selectFkOption(field: string, opt: {id: string; label: string}): void {
    (this.form as any)[field] = opt.id;
    this.fkComboText.update(t => ({ ...t, [field]: opt.label }));
    this.fkComboOpen.update(o => ({ ...o, [field]: false }));
  }
$fk_effect_ts
$optional_set_ts
  form: Partial<Row> = { $fields_ts };
  readonly error = signal('');

  handleSubmit(): void {
    $submit_body
      next: (item) => {
        this.silo.setItem(item);
        void this.router.navigate(['/ho_bo/$schema_name/$table_name']);
      },
      error: (err: Error) => this.error.set(err.message),
    });
  }
}
