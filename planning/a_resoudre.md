# À résoudre

## ~~1. Rôles dynamiques — frontend Svelte~~ ✓

Terminé :
- `resource.silo.svelte.ts` : signal `dynamicRoles`, méthode `canUpdateRow(id)`, `refresh()` via endpoint liste pour récupérer `meta.dynamic_roles`, reset systématique.
- `svelte.py` : page detail `canEdit || canUpdateRow(id)`, page access lecture seule (plus de `selectRole`/`auth.login(role)`), `_auth_store` JWT complet, `_layout` trois états.

## 2. Champs FK résolus automatiquement dans les formulaires

`author_id`, `post_id` et autres champs FK portés par le contexte ne devraient pas apparaître dans les formulaires Create/Edit — leur valeur est connue implicitement (utilisateur courant, objet parent).

Piste : une annotation dans le module Python (ex. `@ho_api_auto`) ou une déclaration dans `CRUD_ACCESS` qui marque ces champs comme « auto-resolved » côté backend et les exclut du formulaire généré côté frontend.

## 4. Matrice des permissions — rien ne s'affiche

`PermissionsMatrixComponent` n'affiche aucune ligne. À investiguer : les inputs `roles` et `permissions` sont-ils bien transmis, le composant est-il monté dans le bon contexte, ou y a-t-il une régression liée au changement `activeRoles` → `userRoles` ?

## 3. Admin — droits d'accès hérités par le parent

Quand un verbe est déjà accessible via le rôle parent (ex. `connected` a GET, `author` hérite de `connected`), cliquer sur le verbe pour `author` exige d'abord "+ defined for author" avant de pouvoir configurer les champs. C'est gênant.

Le comportement attendu : si le parent couvre déjà le verbe, la configuration de champs devrait être directement accessible sans étape intermédiaire.
