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

**Usage 2 — barre de recherche universelle (OR sémantique)** : reporté. La barre de recherche actuelle est par colonne (AND). Une vraie recherche cross-field nécessite une évolution de `_parse_q` ou halfORM.

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

## 9. État des filtres `@ho_api_filter` — audit et vérification

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
