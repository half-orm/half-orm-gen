# À résoudre

## ~~1. Rôles dynamiques — frontend Svelte~~ ✓

Terminé :
- `resource.silo.svelte.ts` : signal `dynamicRoles`, méthode `canUpdateRow(id)`, `refresh()` via endpoint liste pour récupérer `meta.dynamic_roles`, reset systématique.
- `svelte.py` : page detail `canEdit || canUpdateRow(id)`, page access lecture seule (plus de `selectRole`/`auth.login(role)`), `_auth_store` JWT complet, `_layout` trois états.

## 2. Champs FK résolus automatiquement dans les formulaires

`author_id`, `post_id` et autres champs FK portés par le contexte ne devraient pas apparaître dans les formulaires Create/Edit — leur valeur est connue implicitement (utilisateur courant, objet parent).

Piste : une annotation dans le module Python (ex. `@ho_api_auto`) ou une déclaration dans `CRUD_ACCESS` qui marque ces champs comme « auto-resolved » côté backend et les exclut du formulaire généré côté frontend.

## 4. Matrice des permissions — refonte

**Diagnostic** : la matrice est toujours vide car :
- Svelte : lit `mod.CRUD_ACCESS` (jamais défini, tout est en DB) → fallback vide
- Angular : lit la DB au moment de `gen frontend`, mais le snapshot est figé

**Décision** :
- Supprimer `<PermissionsMatrix>` des pages list/detail pour les non-admins (redondant avec l'UI)
- Supprimer `permMatrix`, `permRoles` des silos et `permissions-data.ts`
- Réserver la matrice à la vue admin uniquement, alimentée par `/ho_admin/catalog`
- La matrice admin permet de **simuler un rôle** : l'admin clique sur un rôle, `auth.access` est surchargé temporairement, toute l'UI se recalcule (colonnes, boutons, champs) comme si l'utilisateur avait ce rôle — sans que l'API l'honore (JWT admin inchangé). Une bannière indique le mode simulation.

## 5. Rôles dynamiques — résolution systématique pour tous les verbes

Le mécanisme de résolution dynamique des rôles n'est actuellement implémenté que pour GET (liste, affichage `meta.dynamic_roles`) et PUT (handler backend + bouton Edit frontend). Il faut l'étendre à tous les verbes de façon cohérente.

**Cas concret** : si `post_author` a DELETE → pas de bouton Delete pour Alice. Si on voulait n'autoriser POST sur `blog/comment` qu'au propriétaire du post → le bouton Create n'apparaîtrait pas et le handler POST ne validerait pas le rôle dynamique.

**Ce qui manque par verbe :**
- DELETE : `canDeleteRow(id)` côté silo + condition dans les templates list + handler DELETE backend
- POST : `canCreateInContext(parentId?)` côté silo + condition sur le bouton Create + handler POST backend
- GET (filtre) : envisager de filtrer les lignes retournées selon le rôle dynamique (ex. n'afficher que ses propres posts)

**Approche** : généraliser le pattern `canUpdateRow` → `canActionRow(verb, id)`, et côté backend appliquer la résolution dynamique dans tous les handlers (POST, PUT, DELETE) avant le contrôle d'accès.

## 3. Admin — droits d'accès hérités par le parent

Quand un verbe est déjà accessible via le rôle parent (ex. `connected` a GET, `author` hérite de `connected`), cliquer sur le verbe pour `author` exige d'abord "+ defined for author" avant de pouvoir configurer les champs. C'est gênant.

Le comportement attendu : si le parent couvre déjà le verbe, la configuration de champs devrait être directement accessible sans étape intermédiaire.
