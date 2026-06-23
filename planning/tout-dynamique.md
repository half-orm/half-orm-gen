# Plan: API entièrement dynamique + SiloRegistry Angular

## Contexte

L'architecture actuelle génère du code spécifique par relation :
- `api/app.py` : handlers CRUD hardcodés avec TypedDicts par table
- `*.store.ts` : un store Angular par relation (~500 lignes chacun)
- `*.component.ts` : composants list/detail/create par relation

**Problème** : la génération est coûteuse, fragile, et bloque le multi-DB.

**Vision** : halfORM possède déjà **toutes les métadonnées à runtime** via `pg_meta.py`. On peut construire l'API et l'UI entièrement depuis ces métadonnées — sans génération per-relation.

---

## Partie 1 — halfORM : `model.ho_meta()`

**Fichier** : `/home/joel/devel/half-orm/half-orm/half_orm/model.py`

Ajouter une méthode publique `ho_meta()` qui retourne un dict JSON-sérialisable :

```python
def ho_meta(self) -> dict:
    result = {}
    for kind, sfqrn, _ in self.desc():
        dbname, schema, table = sfqrn
        key = f'{schema}/{table}'
        fields_meta = self._fields_metadata(sfqrn)
        fkeys_meta = self._fkeys_metadata(sfqrn)
        pk_fields = self._pkey_constraint(sfqrn)

        fields = []
        for fname, fdata in fields_meta.items():
            fields.append({
                'name': fname,
                'sql_type': fdata['fieldtype'],
                'json_type': _sql_to_json_type(fdata['fieldtype']),  # helper à ajouter
                'is_pk': bool(fdata.get('pkey')),
                'not_null': bool(fdata.get('notnull')),
                'has_default': fdata.get('default_expr') is not None,
            })

        fk_deps, reverse_fks = [], []
        for fk_name, fk_data in fkeys_meta.items():
            ftable_key, ffields, local_fields, upd, del_, is_reverse, is_singleton = fk_data
            _, r_schema, r_table = ftable_key
            entry = {
                'local_fields': local_fields,
                'remote_schema': r_schema,
                'remote_table': r_table,
                'remote_fields': ffields,
            }
            if is_reverse:
                entry['is_singleton'] = is_singleton
                reverse_fks.append(entry)
            else:
                fk_deps.append(entry)

        result[key] = {
            'schema': schema, 'table': table, 'kind': kind,
            'pk_fields': pk_fields,
            'fields': fields,
            'fk_deps': fk_deps,
            'reverse_fks': reverse_fks,
        }
    return result
```

Helper à ajouter (dans `model.py` ou `pg_meta.py`) :
```python
_SQL_TO_JSON = {
    'uuid': 'string', 'text': 'string', 'varchar': 'string', 'bpchar': 'string',
    'int4': 'integer', 'int8': 'integer', 'int2': 'integer',
    'float4': 'number', 'float8': 'number', 'numeric': 'number',
    'bool': 'boolean',
    'date': 'date', 'timestamp': 'datetime', 'timestamptz': 'datetime',
    'jsonb': 'json', 'json': 'json',
}
def _sql_to_json_type(sql_type: str) -> str:
    base = sql_type.lstrip('_')
    return _SQL_TO_JSON.get(base, 'string')
```

---

## Partie 2 — half-orm-gen : API dynamique à runtime

### 2a. Nouveau fichier `half_orm_gen/runtime.py`

Remplace la génération de code par une **fabrique de routes à runtime** :

```python
# half_orm_gen/runtime.py
from litestar import Litestar, get, post, put, delete, Request, Response
from litestar.status_codes import HTTP_204_NO_CONTENT

def build_crud_app(model, module_name: str, api_version: int | None = None, **kwargs) -> Litestar:
    prefix = f'/v{api_version}' if api_version else ''
    handlers = [_ho_meta_handler(model), _ho_access_handler(model), _ho_roles_handler(model)]

    for cls, kind in model.classes():
        crud_access = getattr(cls, 'CRUD_ACCESS', None)
        if not crud_access:
            continue
        handlers.extend(_build_relation_routes(cls, crud_access, prefix))

    # Import custom routes from scaffolded file
    try:
        from api.custom.routes import custom_handlers
        handlers.extend(custom_handlers)
    except ImportError:
        pass

    return Litestar(route_handlers=handlers, **kwargs)
```

**Routes génériques par closures** (capturent `cls` et `crud_access` de la boucle) :

```python
def _build_relation_routes(cls, crud_access, prefix):
    inst = cls()
    schema, table = inst._t_fqrn[1], inst._t_fqrn[2]
    path = f'{prefix}/{schema}/{table}'
    pk_info = _pk_info(cls)  # [(field_name, litestar_type, py_type)]

    handlers = []

    if 'GET' in crud_access:
        @get(path, guards=[...])
        async def list_handler(request: Request, offset: int = 0, limit: int = 100,
                               q: str | None = None) -> dict:
            return await _handle_list(cls, crud_access, request, offset, limit, q)
        handlers.append(list_handler)

    if pk_info and 'GET' in crud_access:
        pk_name, pk_ltype, _ = pk_info[0]
        @get(f'{path}/{{{pk_name}:{pk_ltype}}}', guards=[...])
        async def get_handler(request: Request, **path_params) -> dict:
            return await _handle_get(cls, crud_access, request, path_params[pk_name])
        handlers.append(get_handler)

    # POST, PUT, DELETE similairement...
    return handlers
```

### 2b. `api/app.py` devient un scaffold statique (écrit une fois)

```python
# api/app.py  — scaffoldé une seule fois, jamais régénéré
from half_orm.model import Model
from half_orm_gen.runtime import build_crud_app
from api.custom.middlewares.authorization import AuthMiddleware

model = Model('mydb')
app = build_crud_app(
    model,
    module_name='mydb',
    api_version=1,
    middleware=[AuthMiddleware],
)
```

### 2c. `/ho_meta` endpoint

```python
def _ho_meta_handler(model):
    @get('/ho_meta', guards=[guards.public])
    async def ho_meta() -> dict:
        return model.ho_meta()
    return ho_meta
```

### 2d. `generate.py` simplifié

`GenApi._generate()` :
- **Si `api/app.py` n'existe pas** → scaffolde le fichier minimal ci-dessus
- **Si `api/app.py` existe** → ne touche à rien (les routes sont dynamiques)
- Garde le scaffolding de `api/custom/`, `api/guards.py`, etc.

`crud_routes.py` → supprimé ou gardé pour la rétrocompatibilité FastAPI.

---

## Partie 3 — Angular : SiloRegistry + composants génériques

### 3a. Fichiers partagés (dans `gen_app/assets/angular/` → copiés dans le projet)

**`schema.types.ts`**
```typescript
export interface FieldSchema {
  name: string; sql_type: string; json_type: string;
  is_pk: boolean; not_null: boolean; has_default: boolean;
}
export interface FkDep {
  local_fields: string[]; remote_schema: string; remote_table: string; remote_fields: string[];
}
export interface ResourceSchema {
  schema: string; table: string; kind: string;
  pk_fields: string[]; fields: FieldSchema[];
  fk_deps: FkDep[]; reverse_fks: (FkDep & { is_singleton: boolean })[];
}
export type HoMeta = Record<string, ResourceSchema>;
```

**`resource.silo.ts`**
```typescript
export class ResourceSilo {
  readonly items = signal<Record<string, unknown>[]>([]);
  readonly byId  = signal(new Map<string, Record<string, unknown>>());
  readonly isLoading = signal(false);
  readonly hasMore = signal(true);
  readonly currentOffset = signal(0);
  private loadedFilters = new Map<string, boolean>();

  constructor(
    readonly key: string,           // 'blog/author'
    readonly schema: ResourceSchema,
    private baseUrl: string,        // '/v1/blog/author'
    private http: HttpClient,
    private auth: AuthService,
  ) {}

  list(params: Record<string, unknown> = {}, offset = 0): void { /* même logique qu'avant */ }
  get(id: string): Observable<Record<string, unknown>> { ... }
  create(data: Record<string, unknown>): Observable<Record<string, unknown>> { ... }
  update(id: string, data: Record<string, unknown>): Observable<Record<string, unknown>> { ... }
  remove(id: string): Observable<void> { ... }
  pkValue(item: Record<string, unknown>): string {
    return String(item[this.schema.pk_fields[0]]);
  }
}
```

**`silo-registry.service.ts`**
```typescript
@Injectable({ providedIn: 'root' })
export class SiloRegistry {
  readonly meta = signal<HoMeta>({});
  private silos = new Map<string, ResourceSilo>();

  async init(apiBase: string): Promise<void> {
    const m: HoMeta = await this.http.get<HoMeta>(`${apiBase}/ho_meta`).toPromise();
    this.meta.set(m);
    for (const [key, schema] of Object.entries(m)) {
      const url = `${apiBase}/${key}`;  // '/v1/blog/author'
      this.silos.set(key, new ResourceSilo(key, schema, url, this.http, this.auth));
    }
  }

  get(key: string): ResourceSilo { return this.silos.get(key)!; }
  keys(): string[] { return [...this.silos.keys()]; }
}
```

**`generic-field.component.ts`** — rend un champ selon son `json_type` :
```typescript
// Affiche: string→text, integer/number→right-aligned, boolean→checkbox, date/datetime→formatted
// FK → routerLink vers la ressource distante
// is_pk → font-mono
```

**`generic-list.component.ts`**
```typescript
@Component({ selector: 'generic-list', ... })
export class GenericListComponent {
  resourceKey = input.required<string>();      // 'blog/author'
  filters     = input<Record<string, unknown>>({});
  embedded    = input<boolean>(false);

  private registry = inject(SiloRegistry);
  silo    = computed(() => this.registry.get(this.resourceKey()));
  schema  = computed(() => this.registry.meta()[this.resourceKey()]);
  columns = computed(() => this.schema().fields.filter(f => !f.is_pk || this.schema().pk_fields.length === 1));
}
```

**`generic-detail.component.ts`** / **`generic-create.component.ts`** similairement.

### 3b. Routing dynamique (bootstrap)

```typescript
// app.routes.ts (généré ou bootstrapé dynamiquement)
export function buildRoutes(registry: SiloRegistry): Routes {
  return [
    ...registry.keys().map(key => ({
      path: key,
      component: GenericListComponent,
      data: { resourceKey: key },
    })),
    ...registry.keys().map(key => ({
      path: `${key}/:id`,
      component: GenericDetailComponent,
      data: { resourceKey: key },
    })),
    { path: '', redirectTo: registry.keys()[0], pathMatch: 'full' },
  ];
}
```

### 3c. `gen_app/angular.py` et `gen_store/angular.py` simplifiés

- Copient les fichiers partagés dans `frontend/angular/src/app/generated/`
- Génèrent uniquement le `app.config.ts` avec l'URL de l'API et le `provideRouter([])`
- **Plus aucun fichier par relation**

---

## Ordre d'implémentation

1. **halfORM** : `model.ho_meta()` + `_sql_to_json_type()` (PR sur half-orm)
2. **half-orm-gen API** : `runtime.py` + scaffold `api/app.py` + `/ho_meta` + `generate.py` simplifié
3. **half-orm-gen Angular** : fichiers partagés (`schema.types`, `ResourceSilo`, `SiloRegistry`, composants génériques) + routing dynamique + nettoyage des générateurs per-relation

---

## Vérification

1. Lancer un projet halfORM existant avec `half_orm gen api` → `api/app.py` scaffoldé
2. `GET /ho_meta` → retourne schema JSON complet
3. `GET /v1/blog/author` → liste fonctionnelle
4. `POST /v1/blog/author` → création fonctionnelle
5. `half_orm gen frontend --angular` → copie les fichiers génériques
6. App Angular démarre → `SiloRegistry.init()` appelle `/ho_meta`, construit silos et routes
7. Navigation list/detail/create fonctionne pour toutes les ressources
8. Tester avec une 2e API (multi-DB) : changer l'URL de base → nouvelle UI sans regen

---

## Points ouverts (hors scope immédiat)

- Rendu des champs LaTeX (détecter depuis `sql_type='text'` + description de champ `@latex`)
- Migration des projets existants avec des `app.py` générés
- OpenAPI pour les routes dynamiques (Litestar supporte les hints de type sur `dict` mais moins précis)
- Champs `jsonb` → rendu spécial
