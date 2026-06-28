# Hiérarchie de rôles

## Objectif

Permettre à un rôle d'hériter des droits d'un rôle parent. L'héritage ne peut
qu'élargir les accès : un enfant ne peut pas restreindre ce que son ancêtre a accordé.

## Hiérarchie cible

```
anonymous           (racine — pas de parent)
  └── connected     (tout utilisateur authentifié)
        └── <rôles développeurs>   (ex: author, moderator…)
```

Les rôles système (`anonymous`, `connected`, `admin`) ont `deletable = FALSE`.

## Modèle de données

### DDL — `"half_orm_meta.api".role` (modifié directement dans `ddl.py`)

```sql
CREATE TABLE IF NOT EXISTS "half_orm_meta.api".role (
  name        text PRIMARY KEY,
  deletable   boolean NOT NULL DEFAULT TRUE,
  parent_name text REFERENCES "half_orm_meta.api".role(name)
);
```

Pas de `DEFAULT` sur `parent_name` : halfORM interprète `None` comme "pas de
contrainte sur le champ" (≠ NULL), ce qui causerait une violation FK lors de
l'insert d'`anonymous` si un DEFAULT pointait vers `connected` (non encore créé).
Le défaut `'connected'` pour les nouveaux rôles développeurs est géré dans le
code de l'endpoint `POST /ho_admin/roles`.

Pas de `ON DELETE` : la suppression d'un rôle parent est interdite tant qu'il a
des enfants (PostgreSQL lève une `ForeignKeyViolationError`, renvoyée en HTTP 409
par l'endpoint delete). L'utilisateur doit d'abord réassigner les enfants.

Données initiales insérées au bootstrap :

| name        | deletable | parent_name |
|-------------|-----------|-------------|
| `anonymous` | FALSE     | NULL        |
| `connected` | FALSE     | `anonymous` |
| `admin`     | FALSE     | `connected` |

### Protection contre les cycles

Trigger `BEFORE INSERT OR UPDATE` qui remonte la chaîne `parent_name` et lève une
exception si le rôle courant apparaît parmi ses ancêtres.

---

## Backend

### `ho_api/ddl.py`

- ✅ Colonne `parent_name` ajoutée dans `HO_API_DDL`
- ✅ Trigger anti-cycle `check_role_cycle` ajouté

### `ho_api/loader.py`

- ✅ `load_role_parents(model) -> dict[str, str | None]` ajouté

### `backend/crud_helpers.py` — `_filter_access_for_roles`

- ✅ `_expand_roles(roles, parent_map)` ajouté
- ✅ `_filter_access_for_roles` accepte `parent_map` optionnel

### `ho_admin.py` — endpoints

- ✅ `GET /ho_admin/roles` inclut `parent_name`
- ✅ `POST /ho_admin/roles` — créer un rôle (parent_name défaut `'connected'`)
- ✅ `DELETE /ho_admin/roles/{name}` — supprimer un rôle
- ✅ `PUT /ho_admin/roles/{name}/parent` — changer le parent

### Startup (`runtime.py`)

- ✅ `parent_map_holder` initialisé et rechargé à chaque modification de rôle

---

## Admin UI (Angular)

### Panneau "Roles"

- Afficher `parent_name` sous le nom du rôle (ex : `↳ connected`)
- Permettre de changer le parent via un `<select>` (rôles disponibles sans cycle)
- Bouton "New role" : formulaire avec `name` + `parent_name`

### Panneau "Access rights"

- Les permissions propres au rôle affiché : cochées + actives + modifiables
- Les permissions héritées : cochées + grisées + non modifiables + badge indiquant
  le rôle ancêtre d'où elles proviennent (ex : `↑ anonymous`, `↑ connected`)

#### Données nécessaires

Pour chaque resource/verb/champ, l'UI doit savoir si la permission vient :
- du rôle lui-même → modifiable
- d'un ancêtre précis → lecture seule, badge `↑ <nom_ancêtre>`

**Option retenue** : le backend retourne le catalogue brut par rôle (comme
aujourd'hui) + la chaîne `parent_name`. Le frontend calcule la provenance
client-side en remontant la chaîne et en cherchant quel ancêtre définit
chaque permission en premier.

---

## Sémantique du merge

Le merge dans `_filter_access_for_roles` est déjà une union — aucun changement
de logique. L'expansion de la liste de rôles suffit.

Cas particulier `all_fields_in / all_fields_out = True` hérité : si un ancêtre a
`all_fields_in = True` pour un verb, l'enfant hérite de `all_fields_in = True`
(même si l'enfant n'a pas configuré ce verb).

---

## Ordre d'implémentation

1. ✅ DDL + trigger anti-cycle
2. ✅ `load_role_parents` + `_expand_roles` + `_filter_access_for_roles`
3. ✅ Endpoints admin (create/delete role, set parent)
4. ✅ Admin UI : affichage parent + bouton new role + delete role
5. ✅ Admin UI : marquage visuel des permissions héritées (badge `↑ ancêtre`)
