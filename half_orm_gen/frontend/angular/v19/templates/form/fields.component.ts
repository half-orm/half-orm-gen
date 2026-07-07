import { Component, computed, inject, input } from '@angular/core';
import { RouterLink } from '@angular/router';$latex_import
import type { Row } from '../../resource.silo';
import { SiloRegistry } from '../../silo-registry.service';

@Component({
  selector: '$selector',
  standalone: true,
  imports: [$all_imports],
  templateUrl: './fields.component.html',
  styleUrl: './fields.component.css',
})
export class ${iname}FieldsComponent {
  readonly item    = input.required<Row>();
  readonly hidePk  = input<boolean>(false);
  protected String = String;
  private readonly silo = inject(SiloRegistry).tryGet('$map_key');
  readonly inaccessibleFields = computed(() => this.silo?.inaccessibleFields() ?? new Set<string>());
}
