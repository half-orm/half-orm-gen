import { Component, input } from '@angular/core';

@Component({
  selector: 'ho-tooltip',
  standalone: true,
  host: { class: 'group relative inline-flex' },
  template: `
    <ng-content select="[ho-tooltip-trigger]" />
    <div class="pointer-events-none invisible absolute top-full z-20 mt-2 w-max max-w-xs rounded-lg border border-gray-200 bg-white p-3 text-[11px] leading-relaxed text-gray-700 shadow-lg opacity-0 transition-opacity duration-150 group-hover:visible group-hover:opacity-100"
         [class.left-0]="align() === 'left'" [class.right-0]="align() === 'right'">
      <div class="absolute -top-1 h-2 w-2 rotate-45 border-l border-t border-gray-200 bg-white"
           [class.left-2]="align() === 'left'" [class.right-2]="align() === 'right'"></div>
      <ng-content />
    </div>
  `,
})
export class HoTooltipComponent {
  readonly align = input<'left' | 'right'>('left');
}
