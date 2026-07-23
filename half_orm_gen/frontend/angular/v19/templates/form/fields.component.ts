import { Component, computed, inject, input$fk_core_import } from '@angular/core';
import { RouterLink } from '@angular/router';$latex_import
import type { Row } from '../../resource.silo';
import { SiloRegistry } from '../../silo-registry.service';$fk_label_imports

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
  protected registry = inject(SiloRegistry);
  private readonly silo = this.registry.tryGet('$map_key');
  readonly inaccessibleFields = computed(() => this.silo?.inaccessibleFields() ?? new Set<string>());$fk_label_block
}
