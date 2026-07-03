# À résoudre

## ~~1. Rôles dynamiques — frontend Svelte~~ ✓

Terminé :
- `resource.silo.svelte.ts` : signal `dynamicRoles`, méthode `canUpdate(id)`, `refresh()` via endpoint liste pour récupérer `meta.dynamic_roles`, reset systématique.
- `svelte.py` : page detail `canEdit || canUpdate(id)`, page access lecture seule (plus de `selectRole`/`auth.login(role)`), `_auth_store` JWT complet, `_layout` trois états.

## ~~2. Champs FK résolus automatiquement dans les formulaires~~ ✓

Implémenté via `fk_auto` : table `field_access_fk_auto`, trois types (`connected_user`, `context`, `select`), admin UI Angular, silo signals, runtime injection backend, embedded list New button.

## ~~3. Matrice des permissions — refonte~~ ✓

Réalisé : `<PermissionsMatrix>` supprimée des pages list/detail, matrice réservée à l'admin Angular alimentée par `/ho_admin/catalog`, simulation de rôle (`simulateRole` / `exitSimulation`) avec bannière.

## ~~4. Champs avec valeur par défaut marqués « auto » à tort dans les formulaires PUT~~ ✓

`_is_server_generated_default` dans `ho_admin.py` restreint `fields_with_defaults` aux seules valeurs serveur (`current*`, appels de fonctions `()`). `published DEFAULT false` n'est plus marqué auto et est disponible dans POST IN.

## ~~5. Admin — droits d'accès hérités par le parent~~ ✓

`openPanel` auto-crée l'own entry si hérité, `hasAncestorVerb` verrouille la checkbox même après création, warning supprimé sur verbe couvert par un ancêtre.

## ~~6. Rôles dynamiques — résolution systématique pour tous les verbes~~ ✓

Frontend : `canAccess(verb, id)` généralise `canUpdate`/`canDelete` dans les silos Angular et Svelte + templates list/detail.  
Backend DELETE : résolution dynamique ajoutée (pattern identique à PUT — lookup de la ligne, appel des resolvers, ajout du rôle dynamique) + vérification post-résolution que le rôle a bien DELETE.  
Backend POST : pas de résolution dynamique (pas de ligne existante à pre-vérifier) — l'accès est garanti par `_effective_in_fields` qui retourne vide si aucun rôle statique n'a POST.  
GET filtre dynamique (n'afficher que ses propres posts) : hors scope, reporté à une future itération.

## ~~7. Champ « searchable » par field — composant de recherche universel~~ ✓

Table `field_access_searchable` (access_id, field_name). Loader, `_build_access_entry`, `_filter_access_for_roles` propagent `searchable: string[]` dans le GET. Runtime restreint `_parse_q` aux champs searchable quand au moins un est configuré (backward-compat : 0 searchable = tout accepté). Admin UI : section Searchable dans le panneau GET. Silos Angular (`searchableFields` signal) et Svelte (`$derived`). Filter inputs des listes masqués pour les colonnes non-searchable quand le flag est utilisé.

**Searchable hérité** : ✓ `field_access_searchable` étendu avec `role_name` nullable — NULL = même rôle que l'access, non-NULL = rôle enfant bénéficiaire. PK = `(access_id, field_name)`. Loader et `ho_admin.py` distribuent le searchable au bon rôle ; `_searchable_only: True` pour les entrées enfant sans access row propre. Admin UI : `isOwnSearchable`, `isInheritedSearchable`, `_findAccAndRoleForField`, `toggleSearchable` mis à jour.

**Usage 2 — barre de recherche universelle (OR sémantique)** : ✓ Endpoint `GET /ho_search?q=term&limit=5&resource=` (paramètre `resource` optionnel pour filtrer sur une ressource). Angular et Svelte : barre dans le header, dropdown All/ressource, résultats groupés, dropdown se réouvre au focus, navigation détail réactive (`toSignal(route.paramMap)` côté Angular). Lien "see all →" → page dédiée `/ho_bo/search?q=term&r=resource` (OR sémantique, 50 résultats, tous les champs searchable). La page dédiée appelle toujours `ho_search` (jamais le endpoint par ressource directement).

## 8. Scaffold de composants personnalisés — `half_orm gen frontend --list|--edit|--display <schema.table>`

Ajouter des sous-commandes de scaffold pour générer un composant unique sans régénérer tout le frontend :

```bash
half_orm gen frontend --angular --list blog.post      # liste filtrée standalone
half_orm gen frontend --angular --edit blog.post      # formulaire d'édition seul
half_orm gen frontend --angular --display blog.post   # vue lecture seule
```

**Cas d'usage** : intégrer une liste filtrée de `blog.post` dans une page applicative existante (hors backoffice généré), ou générer un composant de sélection pour un FK `select`.

**Ce que ça génère** : le composant Angular/Svelte correspondant (fichier `.ts` + `.html` ou `.svelte`), pré-câblé sur le silo de la ressource, avec les guards d'accès. Le fichier est placé dans un répertoire `custom/` pour ne pas être écrasé par un `gen frontend` complet.

**Lien avec searchable** : le composant `--list` pourrait intégrer automatiquement la barre de recherche si des champs `searchable` sont configurés.

## ~~9. État des filtres `@ho_api_filter` — audit et vérification~~ ✓

Remettre à plat l'état d'avancement des filtres déclarés via `@ho_api_filter`. Points à vérifier :

- Le décorateur `@ho_api_filter` est-il correctement découvert et enregistré au démarrage ?
- Les filtres sont-ils propagés dans `/ho_admin/catalog` (champ `filters` par ressource) ?
- L'admin UI permet-il d'activer/désactiver un filtre par accès (table `access_filter`) ?
- Le handler GET applique-t-il bien le filtre quand il est activé pour le rôle courant ?
- Les filtres apparaissent-ils dans `/ho_access` (frontend peut les connaître) ?

## 10. Protection du dernier admin — backend

La suppression d'un utilisateur ou d'une association `user_role` qui retire le dernier admin laisse le système dans un état irrécupérable (plus personne ne peut accéder à l'interface admin). Le backend doit refuser toute opération (DELETE sur `actor/user`, DELETE sur `half_orm_meta_api/user_role`, PUT qui retire le flag admin) qui ferait tomber à zéro le nombre d'utilisateurs ayant le rôle `admin`.

**Implémentation suggérée** : hook de validation dans les handlers DELETE/PUT des ressources concernées, ou contrainte au niveau du loader qui vérifie `SELECT count(*) FROM user_role WHERE role_name = 'admin'` avant d'appliquer la modification.

## 10. Gestion des erreurs frontend — Angular et Svelte

Les handlers de formulaire (POST, PUT, DELETE) ne gèrent pas les erreurs retournées par le backend (4xx, 5xx). L'utilisateur ne voit rien en cas d'échec.

**À couvrir** :
- Affichage d'un message d'erreur contextuel (inline dans le formulaire ou toast) en cas de 4xx (validation, 403, 409 conflict)
- Gestion des 5xx (message générique, pas de crash silencieux)
- Cas particulier : 401 → redirection vers login ou refresh du token
- Cohérence Angular / Svelte

## 11. Angular généré : `fieldTypes` ne distingue pas les champs booléens

**Où** : `half_orm_gen/frontend/base.py:38-47` (`_field_type_category`), utilisé par
`half_orm_gen/frontend/angular/v19/_list_component.py:150-152` pour générer la map
`fieldTypes` de chaque `list.component.ts` (ex. `blog_post/list.component.ts`).

**Constat** : `FieldType` (dans `stores/filters.ts`) ne connaît que
`'date' | 'datetime' | 'number' | 'string'` — aucune catégorie `'boolean'`.
`_field_type_category` retombe donc sur `'string'` pour tout champ booléen (ex.
`blog.post.published`), alors qu'un helper dédié existe déjà pour détecter ces
champs : `_is_bool_field` (`half_orm_gen/frontend/base.py:50-51`), utilisé par
ailleurs pour générer une checkbox dans les formulaires create/edit
(`_form_components.py`).

**Conséquence** : dans l'écran liste, le filtre sur une colonne booléenne se
comporte comme un filtre texte (`isValidFilterValue`/`matchFilter` dans
`stores/filters.ts` appliquent un `startsWith` insensible à la casse) au lieu
d'un contrôle booléen dédié (case à cocher / tri-state). Pas de crash, mais UX
dégradée et incohérence avec le traitement déjà fait côté formulaire.

**Piste** : ajouter une catégorie `'boolean'` à `FieldType`, la faire remonter
dans `_field_type_category` via `_is_bool_field`, puis adapter `isValidFilterValue`
/ `normalizeFilterValue` / le template du filtre liste pour rendre un contrôle
booléen plutôt qu'un champ texte.
