# Plan : Auto-résolution des champs FK dans les formulaires POST

## Contexte

Certains champs FK requis dans un formulaire POST ont une valeur implicite au moment de la création :
- `author_id` → UUID de l'utilisateur connecté (toujours disponible via JWT)
- `post_id` → UUID du post parent (disponible seulement si on crée un commentaire depuis le détail d'un post)

Ces champs ne doivent pas apparaître dans le formulaire. Le bouton "New" ne doit s'afficher que si tous les champs FK de type `context` sont résolus par le contexte courant (embedded list avec filtres).

La configuration est stockée en DB et gérée via l'UI admin (panneau field access), pas dans le code Python.

---

## Architecture

### Trois types de résolveurs

| Type | Formulaire | Résolution |
|------|-----------|------------|
| `connected_user` | caché | **backend** injecte PK de `request.state.user` (JWT) |
| `context` | caché | **frontend** envoie depuis `filters` de la liste embedded |
| `select` | visible — `<select>` peuplé depuis ressource cible | **utilisateur** choisit (ex. assignation d'un ticket) |

### Nouveau format `crud_access` (en mémoire)

```python
'POST': {
  'connected': {
    'in':  ['title', 'content', 'post_id', 'author_id'],
    'fk_auto': {'author_id': 'connected_user', 'post_id': 'context'},
  }
}
```

---

## 1. Backend — DB

### `half_orm_gen/backend/ho_api/ddl.py`

Ajouter la table après `access_filter` :

```sql
CREATE TABLE IF NOT EXISTS "half_orm_meta.api".field_access_fk_auto (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  access_id    uuid NOT NULL REFERENCES "half_orm_meta.api".access(id) ON DELETE CASCADE,
  field_name   text NOT NULL,
  resolve_rule text NOT NULL CHECK (resolve_rule IN ('connected_user', 'context', 'select')),
  UNIQUE (access_id, field_name)
);
```

### `half_orm_gen/backend/ho_api/models.py`

Ajouter `field_access_fk_auto()` accessor (même pattern que `field_access_in`, `field_access_out`).

---

## 2. Backend — Loader

### `half_orm_gen/backend/ho_api/loader.py`

Après le chargement de `in_rows` / `out_rows`, lire `field_access_fk_auto` :

```python
fk_rows = await api.field_access_fk_auto()(access_id=acc_id).ho_aselect('field_name', 'resolve_rule')
if fk_rows:
    entry['fk_auto'] = {r['field_name']: r['resolve_rule'] for r in fk_rows}
```

---

## 3. Backend — Admin endpoints

### `half_orm_gen/backend/litestar/v2/ho_admin.py`

#### Catalog — étendre `ResourceInfo`

Dans la construction du catalog (`/ho_admin/catalog`), pour chaque ressource :
- Ajouter `fk_deps` : itérer sur `rel_inst._ho_fkeys` **sans skipper les FK composites** (contrairement à `_fk_deps()` de `base.py` qui les ignore)
  - Format : `[{'fields': ['author_id'], 'target': 'actor/user', 'target_fields': ['id']}, {'fields': ['schema_name', 'table_name'], 'target': 'half_orm_meta_api/route', 'target_fields': ['schema_name', 'table_name']}, ...]`
  - Chaque entrée représente une FK, simple ou composite
- Dans chaque `AccessEntry`, ajouter `fk_auto` depuis `field_access_fk_auto`

#### Règle pour les FK composites

Un groupe de champs FK (ex. `['schema_name', 'table_name']`) partage toujours la même règle. La table `field_access_fk_auto` stocke un row par champ, mais tous les champs d'un groupe reçoivent la même `resolve_rule` simultanément (l'admin UI les traite comme une unité).

#### Nouveaux endpoints

```
POST   /ho_admin/field_access_fk_auto
       Payload: {access_id, field_name, resolve_rule}

DELETE /ho_admin/field_access_fk_auto/{access_id}/{field_name}
```

Pattern identique à `field_access_in` / `access_filter` : `ho_ainsert()` → `_reload(resource)`.

---

## 4. Backend — Handler POST

### `half_orm_gen/backend/litestar/v2/runtime.py`

Dans `_make_post_handler`, après avoir calculé `payload` :

```python
fk_auto = {}
for role in roles:
    fa = crud_access.get('POST', {}).get(role, {})
    if isinstance(fa, dict):
        fk_auto.update(fa.get('fk_auto', {}))

for field, rule in fk_auto.items():
    if rule == 'connected_user':
        # Injecter PK depuis JWT, retirer du payload client si présent
        payload.pop(field, None)
        user_id = getattr(request.state, 'user_id', None) or (request.state.user or {}).get('id')
        if user_id:
            payload[field] = user_id
    # 'context' : le client envoie la valeur (déjà dans payload via in_fields)
```

---

## 5. Backend — `/ho_access`

Localiser l'endpoint `/ho_access` dans `runtime.py` (ou fichier dédié). Étendre sa réponse pour inclure `fk_auto` par verb/role :

```json
{
  "blog/post": {
    "POST": { "in": ["title", "content"], "fk_auto": {"author_id": "connected_user"} }
  },
  "blog/comment": {
    "POST": { "in": ["content", "post_id", "author_id"], "fk_auto": {"author_id": "connected_user", "post_id": "context"} }
  }
}
```

---

## 6. Frontend Angular — Silo

### `half_orm_gen/frontend/angular/v19/resource.silo.ts`

Ajouter trois éléments :

```typescript
readonly fkAutoPostFields: Signal<Record<string, string>>;
readonly fkAutoPutFields:  Signal<Record<string, string>>;  // pour masquage PUT

// Dans le constructeur :
this.fkAutoPostFields = computed(() =>
  (auth.effectiveAccess() as any)[key]?.POST?.fk_auto ?? {}
);
this.fkAutoPutFields = computed(() =>
  (auth.effectiveAccess() as any)[key]?.PUT?.fk_auto ?? {}
);

// Méthode : le bouton New ne s'affiche que si tous les champs fk_auto:parent
// sont couverts par les filters courants (simples ou composites)
canCreateWithFilters(filters: Record<string, unknown>): boolean {
  if (!this.canCreate()) return false;
  const fkAuto = this.fkAutoPostFields();
  // Pour une FK composite, TOUS ses champs doivent être présents dans filters
  return Object.entries(fkAuto).every(([field, rule]) =>
    rule !== 'context' || !!filters[field]
  );
}
```

Mettre à jour `inaccessiblePostFields` **et** `inaccessiblePutFields` pour masquer les champs `fk_auto` :

```typescript
// Champs fk_auto qui doivent être cachés (auto-injectés) — pas 'select' (visible)
const AUTO_HIDDEN = new Set(['connected_user', 'context']);

// POST : masquer les champs non-in ET les champs fk_auto hidden (connected_user, context)
// Les champs 'select' restent visibles (formulaire dropdown)
this.inaccessiblePostFields = computed(() => {
  const inFields = (auth.effectiveAccess() as any)[key]?.POST?.in as string[] | undefined;
  const fkAuto  = (auth.effectiveAccess() as any)[key]?.POST?.fk_auto ?? {};
  const hiddenFk = Object.keys(fkAuto).filter(f => AUTO_HIDDEN.has(fkAuto[f]));
  const allFields = schema.fields.map(f => f.name);
  if (inFields === undefined) return new Set(hiddenFk);
  if (inFields.length === 0) return new Set(allFields);
  return new Set(allFields.filter(f => !inFields.includes(f) || AUTO_HIDDEN.has(fkAuto[f])));
});

// PUT : masquer les champs non-in ET les champs fk_auto
// (les valeurs FK sont déjà fixées dans l'enregistrement, non éditables)
this.inaccessiblePutFields = computed(() => {
  const allFields = schema.fields.map(f => f.name);
  const fkAuto   = (auth.effectiveAccess() as any)[key]?.PUT?.fk_auto ?? {};
  const staticIn = (auth.effectiveAccess() as any)[key]?.PUT?.in as string[] | undefined;
  const dynIn    = /* fallback dynamicRoles put_in — logique existante */;
  const inFields = staticIn ?? dynIn;
  if (inFields === undefined) return new Set(Object.keys(fkAuto));
  if (inFields.length === 0) return new Set(allFields);
  return new Set(allFields.filter(f => !inFields.includes(f) || !!fkAuto[f]));
});
```

**Règle PUT** : un champ FK marqué `fk_auto` (même `parent`) n'est jamais affiché dans le formulaire d'édition. Sa valeur est déjà dans l'enregistrement et ne change pas.
```

---

## 7. Frontend Angular — Liste

### `half_orm_gen/frontend/angular/v19/_list_component.py`

Remplacer `@if (silo.canCreate())` par `@if (silo.canCreateWithFilters(filters))`.

Le paramètre `filters` est déjà disponible dans le composant list (prop `@Input() filters`).

Dans le composant embedded, `filters` contient `{ post_id: 'uuid-xxx' }` → `canCreateWithFilters` retourne `true`.  
Dans le composant standalone, `filters = {}` → `post_id` manquant → `false`.

---

## 8. Frontend Angular — Formulaire Create

### `half_orm_gen/frontend/angular/v19/_form_components.py`

Dans `handleSubmit` (ou équivalent), après la construction du payload, ajouter les champs `context` depuis les query params de l'URL :

```typescript
// Lire les query params pour les champs fk_auto: context
const urlParams = new URLSearchParams(window.location.search);
for (const [field, rule] of Object.entries(this.silo.fkAutoPostFields())) {
  if (rule === 'context') {
    const val = urlParams.get(field);
    if (val) payload[field] = val;
  }
}
```

### Rendu des champs `select`

Pour chaque champ FK avec `rule === 'select'`, le formulaire doit :
1. Identifier la ressource cible via `fk_deps` du catalog (champ `target`)
2. Fetcher la liste des options depuis l'endpoint list de cette ressource
3. Rendre un `<select>` (ou combobox) avec les options

```typescript
// Signal : champs FK à afficher comme select dans le formulaire POST
readonly fkSelectPostFields: Signal<Record<string, string>>;  // field → target resource key

this.fkSelectPostFields = computed(() => {
  const fkAuto = (auth.effectiveAccess() as any)[key]?.POST?.fk_auto ?? {};
  const fkDeps: FkDep[] = (catalog()[key] as ResourceInfo)?.fk_deps ?? [];
  const result: Record<string, string> = {};
  for (const [field, rule] of Object.entries(fkAuto)) {
    if (rule === 'select') {
      const dep = fkDeps.find(d => d.fields.includes(field));
      if (dep) result[field] = dep.target;
    }
  }
  return result;
});
```

Dans le template de formulaire, pour un champ dont la clé est dans `fkSelectPostFields()`, générer un `<select>` peuplé en fetchant `/{target}/` (toutes les options).

### Bouton "New" dans la liste embedded

Générer le lien avec les query params :

```typescript
// Dans _list_component.py — getter pour l'URL "New"
get newUrl(): string {
  const base = '/ho_bo/{schema_name}/{table_name}/new';
  const fkAuto = this.silo.fkAutoPostFields();
  const params = new URLSearchParams();
  for (const [field, rule] of Object.entries(fkAuto)) {
    if (rule === 'context' && this.filters[field]) {
      params.set(field, String(this.filters[field]));
    }
  }
  const qs = params.toString();
  return qs ? `${base}?${qs}` : base;
}
```

---

## 9. Frontend Angular — Admin UI

### `half_orm_gen/frontend/angular/v19/_ho_admin.py`

#### Interfaces TypeScript

```typescript
interface FkDep {
  fields: string[];        // champs locaux (1 ou plusieurs)
  target: string;          // 'schema/table'
  target_fields: string[]; // champs PK distants
}

interface ResourceInfo {
  // ... champs existants ...
  fk_deps: FkDep[];       // NOUVEAU — inclut FK simples et composites
}

interface AccessEntry {
  // ... champs existants ...
  fk_auto: Record<string, 'connected_user' | 'context' | 'select'>;  // NOUVEAU — un entry par champ local
}
```

#### UI dans le panneau field access (section IN)

Les champs FK sont **groupés** par FK (simple ou composite). Pour chaque groupe FK dont au moins un champ est dans IN :

```html
@for (fk of fkGroupsInPanel(); track fk.target) {
  <div class="border-l-2 border-purple-200 pl-2 mb-2">
    <div class="flex items-center gap-2">
      <span class="text-[9px] text-purple-500 font-semibold">→ {{ fk.target }}</span>
      @if (!panelInheritedFrom()) {
        <select class="text-[9px] border rounded px-1"
                [value]="getFkAutoRule(fk.fields)"
                (change)="setFkAutoGroup(fk.fields, $any($event.target).value)">
          <option value="">—</option>
          <option value="connected_user">connected_user</option>
          <option value="context">context</option>
          <option value="select">select</option>
        </select>
      }
    </div>
    @for (f of fk.fields; track f) {
      <!-- checkbox champ existant, avec opacité réduite si fk_auto défini -->
    }
  </div>
}
```

`fkGroupsInPanel()` = computed qui filtre `panelInfo().fk_deps` pour ne garder que les FK dont au moins un champ apparaît dans `panelInfo().fields`.

#### Méthodes TypeScript

```typescript
getFkAutoRule(fields: string[]): string {
  const fkAuto = this.panelAccess()?.fk_auto ?? {};
  return fkAuto[fields[0]] ?? '';  // tous les champs d'un groupe ont la même règle
}

async setFkAutoGroup(fields: string[], rule: string): Promise<void> {
  const acc = this.panelAccess();
  if (!acc) return;
  for (const field of fields) {
    if (!rule) {
      await fetch(`{version_prefix}/ho_admin/field_access_fk_auto/${acc.id}/${field}`,
        { method: 'DELETE', headers: this._hdrs });
    } else {
      await fetch('{version_prefix}/ho_admin/field_access_fk_auto', {
        method: 'POST',
        headers: { ...this._hdrs, 'Content-Type': 'application/json' },
        body: JSON.stringify({ access_id: acc.id, field_name: field, resolve_rule: rule }),
      });
    }
  }
  await this._reloadCatalog();
}
```

---

## 10. Svelte — Port identique

Même logique dans :
- `half_orm_gen/frontend/svelte/v5/resource.silo.svelte.ts` : `fkAutoPostFields`, `fkAutoPutFields`, `canCreateWithFilters(filters)`
- `half_orm_gen/frontend/svelte/v5/svelte.py` : bouton New avec URL params, `handleSubmit` avec injection parent, masquage PUT des champs fk_auto

---

## Prérequis — clefs composites (à noter dans `planning/a_resoudre.md`)

Avant ou pendant l'implémentation, vérifier que le support des clefs composites est systématisé :
- `getPkId` (liste) et `pkValue()` (silo) gèrent déjà le format `col1:val1::col2:val2`
- Audit à faire : `canUpdate(id)`, `canDelete(id)`, `refresh(id)`, `get(id)`, les routes `[id]`, le formulaire Edit — s'assurer que l'ID composite est bien construit et parsé partout de façon cohérente
- Pour la FK auto-resolve : `canCreateWithFilters(filters)` doit vérifier TOUS les champs d'une FK composite, pas seulement le premier

---

## Ordre d'implémentation recommandé

1. DDL + models (table DB)
2. Loader (lecture en mémoire)
3. Admin endpoints (écriture)
4. Catalog (exposition `fk_deps` + `fk_auto`)
5. `/ho_access` (extension réponse)
6. Runtime POST handler (injection `user`)
7. Silo Angular + Svelte (`fkAutoPostFields`, `canCreateWithFilters`)
8. Admin UI (sélecteur dans panneau field access)
9. Liste (bouton New conditionnel + URL params)
10. Formulaire Create (injection `parent` depuis query params)

---

## Vérification

1. Via admin : marquer `author_id` de `blog/post` POST `connected` → `connected_user`, puis `author_id` et `post_id` de `blog/comment` POST `connected` → `connected_user` / `context`
2. Vue liste standalone `blog/comment` : bouton "New" disparaît
3. Vue détail `blog/post` → section `blog/comment` embedded : bouton "New" visible
4. Cliquer "New" : URL = `/ho_bo/blog/comment/new?post_id=<uuid>`, formulaire sans `author_id` ni `post_id`
5. Soumettre : commentaire créé avec `post_id` et `author_id` corrects, sans que l'utilisateur les ait saisis
6. Se connecter en tant qu'Alice : formulaire `blog/post` New ne montre pas `author_id`
