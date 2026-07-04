import { Component, input, output } from '@angular/core';

@Component({
  selector: 'app-new-items-badge',
  standalone: true,
  template: `
    @if (count() > 0) {
      <button type="button" (click)="toggle.emit()"
              class="text-xs font-medium px-2 py-1 rounded-full border transition-colors"
              [class.bg-blue-600]="active()" [class.text-white]="active()" [class.border-blue-600]="active()"
              [class.bg-blue-50]="!active()" [class.text-blue-700]="!active()" [class.border-blue-200]="!active()">
        +{{ count() }} new
      </button>
    }
  `,
})
export class NewItemsBadgeComponent {
  readonly count  = input(0);
  readonly active = input(false);
  readonly toggle = output<void>();
}
