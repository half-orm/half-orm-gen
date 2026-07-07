import { Component, input } from '@angular/core';
import type { Verb, VerbAccess } from './schema.types';

@Component({
  selector: 'app-permissions-fields',
  standalone: true,
  template: `
    @if (access()) {
      <div class="text-xs space-y-2">
        @if (verb() === 'POST' || verb() === 'PUT') {
          <div>
            <div class="text-[10px] font-bold uppercase tracking-widest text-blue-500 mb-1">in</div>
            @if (!access()!.in?.length && !access()!.inherited_in?.length) {
              <em class="text-gray-400">none</em>
            } @else {
              <div class="flex flex-wrap gap-1 max-w-[200px]">
                @for (f of (access()!.in ?? []); track f) {
                  <span class="bg-blue-50 text-blue-700 border border-blue-200 px-1.5 py-0.5 rounded font-mono text-[10px]">{{ f }}</span>
                }
                @for (f of (access()!.inherited_in ?? []); track f) {
                  <span class="bg-gray-50 text-gray-400 border border-gray-200 px-1.5 py-0.5 rounded font-mono text-[10px] italic">{{ f }}</span>
                }
              </div>
            }
          </div>
        }
        <div>
          <div class="text-[10px] font-bold uppercase tracking-widest text-emerald-500 mb-1">out</div>
          @if (!access()!.out?.length && !access()!.inherited_out?.length) {
            <em class="text-gray-400">none</em>
          } @else {
            <div class="flex flex-wrap gap-1 max-w-[200px]">
              @for (f of (access()!.out ?? []); track f) {
                <span class="bg-emerald-50 text-emerald-700 border border-emerald-200 px-1.5 py-0.5 rounded font-mono text-[10px]">{{ f }}</span>
              }
              @for (f of (access()!.inherited_out ?? []); track f) {
                <span class="bg-gray-50 text-gray-400 border border-gray-200 px-1.5 py-0.5 rounded font-mono text-[10px] italic">{{ f }}</span>
              }
            </div>
          }
        </div>
      </div>
    }
  `,
})
export class PermissionsFieldsComponent {
  readonly access = input<VerbAccess | undefined>(undefined);
  readonly verb   = input<Verb>('GET');
}
