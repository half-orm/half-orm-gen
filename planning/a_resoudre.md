# À résoudre

## ~~1. Rôles dynamiques — frontend Svelte~~ ✓

Terminé :
- `resource.silo.svelte.ts` : signal `dynamicRoles`, méthode `canUpdate(id)`, `refresh()` via endpoint liste pour récupérer `meta.dynamic_roles`, reset systématique.
- `svelte.py` : page detail `canEdit || canUpdate(id)`, page access lecture seule (plus de `selectRole`/`auth.login(role)`), `_auth_store` JWT complet, `_layout` trois états.

## ~~2. Champs FK résolus automatiquement dans les formulaires~~ ✓

Implémenté via `fk_auto` : table `field_access_fk_auto`, trois types (`connected_user`, `context`, `select`), admin UI Angular, silo signals, runtime injection backend, embedded list New button.

## ~~3. Matrice des permissions — refonte~~ ✓

Réalisé : `<PermissionsMatrix>` supprimée des pages list/detail, matrice réservée à l'admin Angular alimentée par `/ho_admin/catalog`, simulation de rôle (`simulateRole` / `exitSimulation`) avec bannière.

## 4. Champs avec valeur par défaut marqués « auto » à tort dans les formulaires PUT

`_is_server_generated` traite comme auto tout champ ayant une valeur par défaut DB (ex. `published DEFAULT false`), ce qui les exclut des formulaires d'édition. Ce traitement doit être réservé aux clefs primaires et aux champs générés par le serveur (séquences, `DEFAULT gen_random_uuid()`, etc.). Les champs avec une simple valeur par défaut doivent rester éditables.

## ~~5. Admin — droits d'accès hérités par le parent~~ ✓

`openPanel` auto-crée l'own entry si hérité, `hasAncestorVerb` verrouille la checkbox même après création, warning supprimé sur verbe couvert par un ancêtre.

## ~~6. Rôles dynamiques — résolution systématique pour tous les verbes~~ ✓

Frontend : `canAccess(verb, id)` généralise `canUpdate`/`canDelete` dans les silos Angular et Svelte + templates list/detail.  
Backend DELETE : résolution dynamique ajoutée (pattern identique à PUT — lookup de la ligne, appel des resolvers, ajout du rôle dynamique) + vérification post-résolution que le rôle a bien DELETE.  
Backend POST : pas de résolution dynamique (pas de ligne existante à pre-vérifier) — l'accès est garanti par `_effective_in_fields` qui retourne vide si aucun rôle statique n'a POST.  
GET filtre dynamique (n'afficher que ses propres posts) : hors scope, reporté à une future itération.

## 7. Champ « searchable » par field — composant de recherche universel

Ajouter un flag `searchable` par champ **par accès/rôle** dans l'interface Admin. Ce flag indique quels champs peuvent être utilisés pour filtrer/rechercher les enregistrements d'une ressource via `?q=...`.

**Usage 1 — select FK** : pour les champs FK de type `select` dans les formulaires Create, peupler le combobox en recherchant sur les champs `searchable` de la ressource cible. Sans ce flag, on doit charger toutes les lignes (non scalable).

**Usage 2 — recherche universelle sur les listes** : n'importe quelle vue liste peut exposer une barre de recherche dès qu'au moins un champ est marqué `searchable`. Le flag contrôle aussi **qui peut chercher quoi** : un rôle peut avoir GET sur une ressource mais être limité à zéro champ searchable (liste possible, recherche interdite), ou avoir accès à un sous-ensemble de champs filtrables.

**Niveau de stockage** : par accès/rôle (comme `field_access_in`/`field_access_out`), pas global par ressource — ce qui permet la granularité par rôle.

**À propager** : dans le catalog `/ho_admin/catalog`, dans `/ho_access` (par verb GET), et dans les silos frontend (`searchableFields` signal).

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

## 9. Protection du dernier admin — backend

La suppression d'un utilisateur ou d'une association `user_role` qui retire le dernier admin laisse le système dans un état irrécupérable (plus personne ne peut accéder à l'interface admin). Le backend doit refuser toute opération (DELETE sur `actor/user`, DELETE sur `half_orm_meta_api/user_role`, PUT qui retire le flag admin) qui ferait tomber à zéro le nombre d'utilisateurs ayant le rôle `admin`.

**Implémentation suggérée** : hook de validation dans les handlers DELETE/PUT des ressources concernées, ou contrainte au niveau du loader qui vérifie `SELECT count(*) FROM user_role WHERE role_name = 'admin'` avant d'appliquer la modification.

## 10. Gestion des erreurs frontend — Angular et Svelte

Les handlers de formulaire (POST, PUT, DELETE) ne gèrent pas les erreurs retournées par le backend (4xx, 5xx). L'utilisateur ne voit rien en cas d'échec.

**À couvrir** :
- Affichage d'un message d'erreur contextuel (inline dans le formulaire ou toast) en cas de 4xx (validation, 403, 409 conflict)
- Gestion des 5xx (message générique, pas de crash silencieux)
- Cas particulier : 401 → redirection vers login ou refresh du token
- Cohérence Angular / Svelte
