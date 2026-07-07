import { Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { SiloRegistry } from '../../generated/silo-registry.service';
import { FieldSchema, FkDep } from '../../generated/schema.types';
interface ResourceView {
  key: string;
  table: string;
  kind: string;
  fields: (FieldSchema & { fkTarget: string | null })[];
  reverseFks: string[];
}

@Component({
  selector: 'app-schema',
  standalone: true,
  imports: [RouterLink],
  styles: [':host { display: flex; height: 100%; overflow: hidden; }'],
  template: `
    <aside class="w-max shrink-0 overflow-y-auto border-r bg-white flex flex-col">
      <div class="px-3 pt-3 pb-2 border-b">
        <input [value]="tocFilter()" (input)="tocFilter.set($$any($$event).target.value)"
               placeholder="Filter…"
               class="w-full text-xs border rounded px-2 py-1 text-gray-700"/>
      </div>
      <div class="px-3 py-3 space-y-4 flex-1">
        @for (schema of filteredSchemas(); track schema.name) {
          <div>
            <a (click)="scrollTo('s__' + schema.name)"
               class="block text-xs font-semibold text-gray-500 uppercase tracking-wide hover:text-gray-800 cursor-pointer mb-1">
              {{ schema.name }}
            </a>
            <ul class="space-y-0.5 pl-2">
              @for (res of schema.resources; track res.key) {
                <li>
                  <a (click)="scrollTo(res.key.replace('/', '_'))"
                     class="text-sm text-blue-600 hover:underline cursor-pointer">{{ res.table }}</a>
                </li>
              }
            </ul>
          </div>
        }
      </div>
    </aside>

    <div class="flex-1 overflow-y-auto px-6 py-6 space-y-10">
      <h1 class="text-2xl font-bold text-gray-800">Database Schema</h1>
      @for (schema of schemas(); track schema.name) {
        <section [id]="'s__' + schema.name">
          <h2 class="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-3 border-b pb-1">
            {{ schema.name }}
          </h2>
          <div class="space-y-4">
            @for (res of schema.resources; track res.key) {
              <div class="bg-white border rounded-lg overflow-hidden" [id]="res.key.replace('/', '_')">
                <div class="flex items-center gap-2 px-4 py-2 bg-gray-50 border-b">
                  <a [routerLink]="'/ho_bo/' + res.key"
                     class="font-semibold text-blue-700 hover:underline">{{ res.table }}</a>
                  <span class="text-xs text-gray-400 border rounded px-1">{{ res.kind }}</span>
                </div>
                <table class="w-full text-sm">
                  @for (field of res.fields; track field.name) {
                    <tr class="border-b last:border-b-0 hover:bg-gray-50">
                      <td class="px-4 py-1.5 font-mono text-xs w-1/3"
                          [class.font-bold]="field.is_pk"
                          [class.text-amber-700]="field.is_pk">
                        {{ field.is_pk ? '[PK] ' : '' }}{{ field.name }}
                      </td>
                      <td class="px-4 py-1.5 text-gray-500 text-xs w-1/4">{{ field.sql_type }}</td>
                      <td class="px-4 py-1.5 text-xs">
                        @if (field.fkTarget) {
                          <a (click)="scrollTo(field.fkTarget!.replace('/', '_'))"
                             class="text-blue-600 hover:underline cursor-pointer">&rightarrow; {{ field.fkTarget }}</a>
                        }
                      </td>
                    </tr>
                  }
                  @if (res.reverseFks.length > 0) {
                    <tr class="bg-gray-50 border-b">
                      <td colspan="3" class="px-4 py-1 text-xs font-semibold text-gray-400 uppercase tracking-wide">
                        Referenced by
                      </td>
                    </tr>
                    @for (rfk of res.reverseFks; track rfk) {
                      <tr class="border-b last:border-b-0 hover:bg-gray-50">
                        <td colspan="2"></td>
                        <td class="px-4 py-1.5 text-xs">
                          <a (click)="scrollTo(rfk.replace('/', '_'))"
                             class="text-indigo-500 hover:underline cursor-pointer">&leftarrow; {{ rfk }}</a>
                        </td>
                      </tr>
                    }
                  }
                </table>
              </div>
            }
          </div>
        </section>
      }
    </div>
  `,
})
export class SchemaComponent {
  protected registry = inject(SiloRegistry);

  tocFilter = signal('');

  scrollTo(id: string): void {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
  }

  readonly schemas = computed(() => {
    const meta = this.registry.meta();
    const bySchema = new Map<string, ResourceView[]>();
    for (const [key, res] of Object.entries(meta)) {
      if (!bySchema.has(res.schema)) bySchema.set(res.schema, []);
      const fkByField = new Map<string, string>();
      for (const fk of res.fk_deps as FkDep[]) {
        for (const lf of fk.local_fields) {
          fkByField.set(lf, `$${fk.remote_schema}/$${fk.remote_table}`);
        }
      }
      bySchema.get(res.schema)!.push({
        key,
        table: res.table,
        kind: res.kind,
        fields: (res.fields as FieldSchema[]).map(f => ({
          ...f,
          fkTarget: fkByField.get(f.name) ?? null,
        })),
        reverseFks: (res.reverse_fks as (FkDep & { is_singleton: boolean })[])
          .map(rfk => `$${rfk.remote_schema}/$${rfk.remote_table}`),
      });
    }
    return [...bySchema.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([name, resources]) => ({
        name,
        resources: resources.sort((a, b) => a.table.localeCompare(b.table)),
      }));
  });

  readonly filteredSchemas = computed(() => {
    const q = this.tocFilter().toLowerCase().trim();
    if (!q) return this.schemas();
    return this.schemas()
      .map(s => ({
        ...s,
        resources: s.name.toLowerCase().includes(q)
          ? s.resources
          : s.resources.filter(r => r.table.toLowerCase().includes(q)),
      }))
      .filter(s => s.resources.length > 0);
  });
}
