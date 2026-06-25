def _schema_component_spec_ts() -> str:
    return """\
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { signal } from '@angular/core';
import { SchemaComponent } from './schema.component';
import { SiloRegistry } from '../../generated/silo-registry.service';

const MOCK_META = {
  'public/project': {
    schema: 'public', table: 'project', kind: 'table',
    pk_fields: ['id'],
    fields: [{ name: 'id', sql_type: 'uuid', is_pk: true }],
    fk_deps: [],
    reverse_fks: [],
  },
};

function makeRegistry() {
  return { meta: signal(MOCK_META), get: () => null, tryGet: () => null };
}

describe('SchemaComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SchemaComponent],
      providers: [
        provideRouter([]),
        { provide: SiloRegistry, useValue: makeRegistry() },
      ],
    }).compileComponents();
  });

  it('creates', () => {
    const fixture = TestBed.createComponent(SchemaComponent);
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('table title link navigates to /ho_bo/schema/table (not encoded)', () => {
    const fixture = TestBed.createComponent(SchemaComponent);
    fixture.detectChanges();
    const link: HTMLAnchorElement = fixture.nativeElement.querySelector('a.font-semibold.text-blue-700');
    expect(link).toBeTruthy();
    expect(link.getAttribute('href')).toBe('/ho_bo/public/project');
  });

  it('shows table name and kind', () => {
    const fixture = TestBed.createComponent(SchemaComponent);
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('project');
    expect(fixture.nativeElement.textContent).toContain('table');
  });

  it('TOC filter hides non-matching resources', () => {
    const fixture = TestBed.createComponent(SchemaComponent);
    fixture.detectChanges();
    fixture.componentInstance.tocFilter.set('xxx');
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('a.font-semibold.text-blue-700')).toBeNull();
  });
});
"""
