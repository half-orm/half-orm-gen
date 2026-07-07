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

## ~~12. Export/import de la configuration d'accès admin~~ ✓

**Constat** : toute la configuration faite via l'Admin UI (roles, `CRUD_ACCESS`
par accès, `field_access_in/out`, `field_access_fk_auto`, `field_access_searchable`,
`field.label_order`, `access_filter`) vit dans les tables `half_orm_meta.api.*`
— une donnée applicative, pas régénérée par `half_orm gen`. Un
`make demo-blog`/`demo-blog-clean` (drop DB + regen complet) efface donc
systématiquement toute cette configuration, ce qui oblige à tout reconfigurer
à la main dans l'Admin UI après chaque cycle de dev — source d'erreurs
d'oubli (ex. label field pas reconfiguré après un rebuild, cf. session du
2026-07-04).

**Terminé** : pas de JSON/endpoint — un simple dump SQL suffit. Deux cibles
Makefile :
- `make demo-blog-access-save` — `pg_dump --data-only --inserts` sur les
  tables réellement admin-configurées (`access`, `field_access_in/out`,
  `field_access_fk_auto`, `field_access_searchable`, `user_role`), suffixé
  `ON CONFLICT DO NOTHING` (via `sed`) pour rester rejouable. `role`, `route`,
  `field` et `filter` sont **exclues** : auto-peuplées par l'app au démarrage
  (rôles système + `discover_and_register`, scan des `CRUD_ACCESS`/`@ho_api_filter`
  du code) — jamais purement admin, jamais stables à dumper telles quelles.
  `filter.id` en particulier change de valeur à chaque redémarrage
  (`gen_random_uuid()` côté auto-insert) : `access_filter` est donc généré à
  part, résolu par la clé naturelle du filtre (`schema_name`, `table_name`,
  `name`) via une sous-requête au chargement, pas par son id. Même souci
  contourné pour `field.label_order` (la ligne `field` existe déjà, auto-créée)
  via des `UPDATE` générés plutôt qu'un `INSERT`.
- `make demo-blog-access-load` — `psql -f fixtures/blog_demo_access.sql`,
  rejoué automatiquement (jusqu'à 5 fois, 2s d'intervalle) si le premier
  essai échoue : rien ne garantit qu'un rôle dynamique comme `post_author`
  (enregistré par `discover_and_register` au démarrage de l'API) soit déjà
  en base au moment exact où le rechargement est lancé — plutôt que de
  deviner ce timing, on réessaie tant que le fichier n'est pas totalement
  rejoué (idempotent grâce à `ON CONFLICT DO NOTHING`, donc sans risque de
  double-insertion sur les tentatives déjà réussies).

  `crud_access_by_res`/`access_map_holder` sont lus depuis la base une seule
  fois au démarrage (`build_crud_app`) — un chargement fait directement en
  SQL (hors `/ho_admin/*`) est invisible pour un process déjà lancé, sans
  quoi toutes les routes CRUD renvoient 403 malgré une base correctement
  rechargée. Premier essai : tuer puis relancer le process API depuis la
  cible Make. Abandonné — deux façons différentes de mal tourner en le
  testant (conflit de port par `litestar run --reload` qui lance uvicorn
  comme sous-processus enfant, tuer le PID du wrapper ne tue pas forcément
  l'enfant qui garde le port ; puis un blocage non expliqué du redémarrage
  automatique lui-même).

  **Solution retenue : `SIGHUP`**, le signal conventionnel "recharge ta
  config" (nginx, postgres, ...), plutôt que tuer/relancer le process.
  `build_crud_app` (`runtime.py`) extrait la logique de `_startup` dans
  `_reload_all_access()` (partagée par le démarrage et le rechargement à
  chaud) et enregistre un handler asyncio sur `SIGHUP` qui la rappelle puis
  rediffuse `{'event': 'access_reload'}` en WebSocket (même mécanisme que
  les mutations `/ho_admin/*`, donc les sessions déjà ouvertes se
  rafraîchissent aussi). `demo-blog-access-load` envoie le signal par motif
  de ligne de commande (`pgrep -f 'uvicorn.*demos/blog_demo/ho_api'`), pas
  via `api.pid` : le handler tourne dans le sous-processus uvicorn enfant,
  pas dans le process wrapper dont le PID est capturé.

  Piège rencontré en testant : `pkill -f`/`pgrep -f` matchent la ligne de
  commande *complète* de chaque process — y compris celle du shell qui
  exécute la recette elle-même, puisque le texte de la recette (passé à
  `sh -c '...'`) contient littéralement le motif recherché en tant que
  sous-chaîne. Le premier essai s'auto-`SIGHUP`-ait donc lui-même
  immédiatement après le chargement SQL. Corrigé en excluant explicitement
  le PID du shell courant (`grep -vx "$$$$"`, `$$$$` → PID du shell) du
  résultat de `pgrep` avant d'envoyer le signal.

  Deuxième piège : même en excluant le shell, le signal n'atteignait pas le
  handler — `demo-blog-api-run` utilisait `litestar run --debug --reload`,
  et `--reload` ajoute son propre superviseur + worker (PID du worker
  instable, recréé au moindre changement détecté) par-dessus l'écart
  wrapper-vs-enfant déjà présent sans lui. Corrigé en retirant `--reload` :
  un seul process uvicorn stable, cible fiable pour `pgrep`/`SIGHUP` — perte
  acceptable puisque `--reload` ne surveille que `ho_api/`, jamais le paquet
  `half_orm_gen` installé (il n'a jamais aidé à charger les modifs de cette
  session de toute façon, cf. l'épisode de l'install éditable pointant sur
  un commit figé).

  Nettoyage au passage : `roles_set`, calculé dans l'ancien `_startup` mais
  jamais utilisé, supprimé pendant l'extraction. Et un bug latent corrigé —
  `pk_names_startup` lisait `pk_info` par fermeture (valeur de la *dernière*
  ressource de la boucle de construction des routes, pas celle en cours de
  traitement) ; `_reload_all_access` recalcule `_pk_info(cls)` pour chaque
  ressource.

**Effet de bord découvert en testant** : `ho_api/.env` est scaffoldé une
seule fois par half-orm-gen avec un `HO_JWT_SECRET` aléatoire, mais
`--cleanup` supprime tout le projet (ce fichier compris) — chaque rebuild
générait donc un secret différent, invalidant tout token JWT déjà stocké
dans le navigateur et forçant une reconnexion à chaque itération. Fixé dans
`demo_blog.sh` : `ho_api/.env` reçoit une valeur stable
(`blog_demo_dev_secret_do_not_use_in_production`) après `half_orm gen api`,
pas pour la sécurité (aucun enjeu ici) mais pour garder les sessions
existantes valides d'un rebuild à l'autre.

Limite connue : simple, pas un vrai outil de migration — suffisant pour
l'usage visé (recharger la config de dev après un `make demo-blog-clean`).

**Bug trouvé en testant le rechargement à chaud** : la page détail (et donc
aussi l'édition, qui est le même composant) ne se rafraîchissait pas toute
seule après un `access_reload` sans ressource précise (rechargement global,
notre cas SIGHUP) — son effect ne lisait que `resourceAccessVersion()[map_key]`,
pas le compteur global `accessVersion()`, contrairement à celui de la liste
qui lit déjà les deux. `_detail_component.py` et `svelte.py::_detail_page`
corrigés pour lire aussi `accessVersion()`, comme la liste.

**Reste à traiter séparément (pas urgent)** : sur le formulaire de création,
l'effect qui précharge les options du combobox FK (`fkOptions`) relit bien
`fkAutoFields('POST')` de façon réactive, mais l'appel `.list()` sous-jacent
est dédupliqué par URL (`ResourceSilo.fetchedRoutes`) — si la table *cible*
du FK a déjà été chargée une fois dans la session, un changement d'accès qui
modifierait les lignes visibles dans cette table cible ne se re-fetch pas.
Cas étroit (il faut que les droits sur la ressource cible du FK changent en
cours de session), pas traité pour l'instant.

## 14. Architecture des générateurs — séparer logique partagée et rendu par framework

**Constat** : `_list_component.py` (Angular) et `svelte.py` (Svelte)
dupliquent la même logique de génération (quels champs boucler, quelles
conditions déclenchent quel bloc — ex. `filter_inputs`/`action_filter_th`)
sous deux formes de rendu distinctes. Cette session en a donné une preuve
concrète : la correction du tooltip d'aide au filtre (style, centrage,
regroupement en composant réutilisable) a dû être appliquée deux fois,
une par générateur, avec le risque d'oubli que ça implique.

**Constat additionnel** : le rendu texte, lui, ne peut pas être partagé
tel quel — Angular (`@if`/`@for`, `[value]="x"`, `(click)="f()"`,
`<ng-content select="[x]">`) et Svelte (`{#if}`/`{#each}`, `value={x}`,
`onclick={() => f()}`, `{#snippet}`/`{@render}`) divergent trop en syntaxe
pour un même gabarit f-string.

**Piste retenue** : extraire la partie purement logique (quels champs,
quelles conditions, dans quel ordre) dans une fonction Python partagée
utilisée par les deux générateurs, et ne garder que le rendu texte final
(fin, spécifique à chaque syntaxe) séparé par framework. Complémentaire à
deux autres principes déjà adoptés dans cette session, à appliquer au fil
de l'eau (pas de chantier dédié) :
- privilégier de vrais templates multi-lignes (f-string triple-quotée par
  bloc répété, lisible comme du HTML réel) plutôt que des fragments `f'...'`
  concaténés bout à bout (cf. `_filter_th` dans le nouveau style) ;
- sortir tout bloc UI générique et non spécifique à la ressource (ex.
  `HoTooltipComponent`/`Tooltip.svelte`, la modale JSON dans les listes)
  dans un vrai composant Angular/Svelte partagé, plutôt que de le
  régénérer en HTML brut à chaque ressource.

## 15. Essai avorté — logique partagée Angular/Svelte pour le composant de recherche globale

**Contexte** : en appliquant le principe de l'item 14 au composant de
recherche globale (barre de recherche du header + page `/ho_bo/search`),
on a comparé le corps des fonctions/computed concernées —
`searchableResources`, `hasGlobalSearch`, `runSearch`, `goToDetail`,
`formatResult`, `searchResultEntries` — entre
`half_orm_gen/frontend/angular/v19/_app_shell.py` et
`half_orm_gen/frontend/svelte/v5/svelte.py`.

**Constat** : la logique est bien structurellement identique, mais diffère
mécaniquement à quasiment chaque ligne : lecture de signal Angular
`this.x()` (à l'intérieur de `computed(() => ...)`) vs lecture de rune
Svelte, simple identifiant `x` (à l'intérieur de `$derived(...)`) ;
`this.auth.effectiveAccess()` vs `auth.access` ; `this.router.navigate([...])`
vs `goto(...)` ; `this.registry.meta()` vs `registry.meta`. Partager le
texte tel quel demanderait une couche d'adaptation/substitution
ligne-à-ligne pour chacune de ces différences mécaniques — un coût réel
pour un premier essai isolé.

**Décision** : laissé à l'état de piste, non implémenté. Le bug concret
qui a motivé la discussion (option `All` toujours affichée dans le
sélecteur de ressource, cf. item courant) a été corrigé directement dans
le code actuel (dupliqué par framework), sans attendre cette
factorisation. À reprendre si l'idée revient sur le tapis, sur les mêmes
fonctions dans les deux fichiers cités.

## ~~16. Notification "nouveaux éléments" — étape 2 : dropdown global dans le header~~ ✓

**Fait (session du 2026-07-04)** : chaque `ResourceSilo` (Angular
`resource.silo.ts` / Svelte `resource.silo.svelte.ts`) suit désormais les
ids créés depuis l'arrivée sur le site (`newIds`, pas de persistance),
via l'événement WS `create` déjà broadcasté — état 100% en mémoire, remis
à zéro à chaque rechargement de page. Un badge "+N new" (composant dédié
`NewItemsBadgeComponent`/`NewItemsBadge.svelte`, sur le modèle de
`HoTooltipComponent`/`Tooltip.svelte`) s'affiche dans le header de chaque
liste, bascule `showNewOnly` qui filtre `displayItems` aux seuls ids
`silo.isNew(id)`, avec une pastille bleue par ligne concernée. Un élément
est marqué "lu" (`silo.markRead(id)`) quand son composant détail
l'affiche (`item()`/`item` non-null). Les créations faites par le client
lui-même ne sont pas comptées comme nouvelles pour lui
(`ownCreatedIds`, alimenté dans `create()`, consulté avant de marquer
l'écho WS `create` comme nouveau).

**Reste à faire (demain)** : sortir le "+N new" du contexte de la liste
pour en faire un **dropdown global dans le header**, à côté du nom de
connexion — toujours visible, qu'on soit ou non sur la liste concernée.
Cliquer une entrée du dropdown navigue directement vers la liste de la
ressource avec le filtre "new only" pré-appliqué.

Ça demande :
- **Agrégation cross-silo** : un computed dans `SiloRegistry`
  (Angular)/`SiloRegistry` (Svelte) qui somme/liste `newCount` de tous
  les silos actuellement instanciés.
- **Nouveau composant dropdown** dans le header (Angular `_app_shell.py`
  / Svelte `svelte.py`), + navigation avec filtre "new" auto-appliqué sur
  la liste cible (probablement un query param lu par le composant liste
  pour initialiser `showNewOnly` à `true`).

Point vérifié (2026-07-05), pas besoin de traitement particulier :
`SiloRegistry.init()` (Angular ET Svelte) crée déjà un `ResourceSilo` pour
**toutes** les ressources de `meta()` dès le démarrage, pas paresseusement
via `.get()` — donc toute ressource, même jamais visitée pendant la
session, a déjà son silo actif et son suivi `newIds` dès le chargement de
l'app. Pas de mécanisme de "création à froid sur événement WS" à ajouter,
et donc pas de changement `Subject` → `ReplaySubject` nécessaire côté
Angular. Fausse piste d'hier, corrigée après vérification du code.

**Fait en préalable (2026-07-05)** : les événements WS (`create`/`update`/
`delete`/`access_reload`) portent désormais un timestamp `ts` (epoch ms,
compatible `new Date(ts)`/`Date.now()` côté JS) — nouveau helper partagé
`_ws_event(event, resource=None, id=None, **extra)` dans
`half_orm_gen/backend/crud_helpers.py`, utilisé par les deux runtimes
(`litestar/v2/runtime.py`, `litestar/v2/ho_admin.py`,
`fastapi/v0/runtime.py`) et par `_ws_broadcast_cascade`. Objectif immédiat :
afficher une récence ("il y a 2 min") dans le futur dropdown global.

**Explicitement PAS fait, et pas prévu à ce stade** : rejouer les
événements manqués (ex. après une déconnexion WS) en interrogeant "tout
ce qui s'est passé depuis T". Le WS reste purement transitoire — aucun
event log persistant côté serveur. Un timestamp sur l'événement ne suffit
pas à lui seul : il faudrait une vraie table/buffer d'événements
interrogeable, **et** décider où vit la notion de "dernière consultation"
par utilisateur (côté backend — une colonne `last_seen_at` liée à
l'utilisateur/la session; ou côté client — un état local par utilisateur,
mais alors non partagé entre appareils). Sujet à part entière, à ne pas
mélanger avec le dropdown de notification "new" (qui reste volontairement
sans persistance, cf. item courant).

## 17. Backend FastAPI en retard sur Litestar — audit de parité à faire

**Constat (2026-07-05)** : en ajoutant le timestamp aux événements WS
(item 16), on a réalisé que `half_orm_gen/backend/fastapi/v0/` n'a **aucun
équivalent de `ho_admin.py`** (absent du répertoire — seuls `runtime.py`,
`scaffold.py`, `templates.py` existent). Autrement dit, tout ce qui a été
construit côté Litestar ces dernières sessions autour de l'admin
(gestion des rôles/CRUD_ACCESS, `field_access_in/out`,
`field_access_fk_auto`, `field_access_searchable`, `field.label_order`,
`access_filter`, rechargement à chaud SIGHUP, `/ho_meta` enrichi avec
`label_fields`, résolution de rôles dynamiques pour PUT/DELETE, etc.)
n'existe probablement pas du tout côté FastAPI — celui-ci n'a
vraisemblablement pas été maintenu depuis un moment.

**Décision** : ne pas traiter maintenant — terminer d'abord le dropdown
global (item 16) en cours. Revenir sur FastAPI dans une session dédiée :
commencer par un audit comparatif complet `litestar/v2/*` vs
`fastapi/v0/*` (fonctionnalité par fonctionnalité) pour mesurer l'écart
réel avant de décider s'il faut porter l'admin complet ou réduire le
périmètre supporté par FastAPI.

## ~~18. Régression — `GET /ho_users` perd les utilisateurs fédérés~~ ✓

**Constat initial (2026-07-06, test live fédération)** : depuis le
déplacement des comptes vers `half_orm_meta.identity."user"` (au lieu de
`actor.user`), plus d'accès aux utilisateurs côté admin.

**Diagnostic affiné** : `ho_users()` (route custom des demos) lisait déjà
correctement `identity.user()` — pas de régression là. Le vrai problème
est plus large : **tout le mécanisme `fk_auto`** (`connected_user`/
`context`/`select`) est cassé pour n'importe quel FK ciblant
`half_orm_meta.identity."user"` (ex. `blog.post.author_id`), pas
seulement la liste d'utilisateurs. Cause : `_fk_deps`/`_reverse_fk_deps`
(`frontend/base.py`) ignorent tout FK dont la cible n'est pas dans
`crud_resources`, lui-même dérivé de `model.classes()` — qui **exclut par
construction** tout schéma préfixé `half_orm_meta` (c'est justement ce qui
permet à `half_orm_meta.identity` de ne pas polluer le CRUD générique).
Résultat : `author_id` n'était même plus détecté comme FK côté admin —
pas de section "FK auto-resolve" du tout, donc ni `connected_user`
(auto-rempli) ni `select` (dropdown) configurables.

**Fait (2026-07-06, option 2 — accès GET réel)** : `half_orm_meta.identity.
"user"` est maintenant traité comme une ressource à part entière, mais
**GET-only** (jamais de POST/PUT/DELETE générés), pilotée par `CRUD_ACCESS`
comme n'importe quelle autre table :

- `runtime.py::build_crud_app` itère `model.classes()` **+** une entrée
  injectée manuellement pour `identity.user()` (via `HoIdentityModels`) —
  seuls `_make_list_handler`/`_make_get_handler` sont générés pour elle ;
  `password_hash` est exclu à la source (`api_excluded = ['password_hash']`,
  filtré par `crud_helpers` quel que soit ce qu'un admin configurerait).
  `_reload_all_access()` itère la même liste combinée.
- `reconcile_catalog`/`/ho_admin/catalog` n'ont rien demandé de plus :
  ils se basent sur `model.ho_meta()` (pas `model.classes()`), qui
  n'exclut *rien* — `identity.user` y était déjà présent, seule la vraie
  route HTTP manquait.
- Les 3 générateurs frontend (`angular.py`, `svelte.py`, `svelte_store.py`)
  ajoutent explicitement `('half_orm_meta.identity', 'user')` à
  `crud_resources`, pour que `_fk_deps` cesse de filtrer `author_id`.
- **Piège rencontré** : `_fk_deps` mutile le nom de schéma cible
  (`.replace('.', '_')`) — inoffensif pour un schéma normal (sans point),
  mais corrompt `half_orm_meta.identity` en `half_orm_meta_identity`, une
  clé que ni la route backend ni `SiloRegistry` (toutes deux basées sur le
  nom réel, avec le point) ne reconnaissent. Non-mutation ciblée ajoutée
  juste après le `.replace()`, uniquement pour cette valeur précise.

**Reste à faire (config, pas du code)** : après régénération, un admin
doit explicitement accorder `GET` sur `half_orm_meta.identity/user` au(x)
rôle(s) concerné(s) (ex. `connected`, champs `out` = `id`/`name`
seulement) et marquer `name` comme label field, pour que le dropdown
"select" affiche des noms plutôt que des uuids bruts.

**Limite connue, pas bloquante** : `reconcile_catalog` insère les 4 verbes
(GET/POST/PUT/DELETE) dans `half_orm_meta.api.route` pour *toute* relation
vue par `model.ho_meta()`, y compris `identity.user` — un admin pourrait
donc voir/cocher POST/PUT/DELETE pour cette ressource dans la matrice de
rôles alors qu'aucune route réelle n'y répond (404 quoi qu'il arrive).
Préexistant (comportement de `reconcile_catalog` inchangé), pas introduit
par ce correctif — non traité ici.

## ~~19. Bug — perte d'identité en naviguant entre les sites de la fédération~~ ✓

**Constat (2026-07-06)** : se connecter sur un peer, puis naviguer vers un
autre site de la fédération, ne conserve pas l'identité — le token vit dans
`sessionStorage`, scopé par origine (donc par site), et la page
`/auth/delegate` redemandait systématiquement email/mot de passe même
quand une session valide existait déjà sur le peer source.

**Fait (2026-07-06)** : `/auth/delegate` (Angular `AuthDelegateComponent` /
Svelte `routes/auth/delegate/+page.svelte`) vérifie maintenant s'il existe
déjà un token local avant d'afficher le formulaire — si oui, il est
directement renvoyé à `redirect_uri` sans redemander les identifiants.
Limite connue (same-tab uniquement) dans
`docs/internals/federation-protocol.md#known-limitation-partial-single-sign-on`.
Complété par l'item 20 : `federationNavUrl` construit désormais un lien de
navigation qui déclenche ce protocole directement (voir ci-dessous),
au lieu de nécessiter de passer par la page de login de l'autre site.

## ~~20. Amélioration — présenter les sites de la fédération pour naviguer (réorg UI)~~ ✓

**Demande** : réorganiser la colonne de gauche du backoffice pour présenter
à l'utilisateur les membres de la fédération comme destinations de
navigation, pas seulement comme configuration admin.

**Fait (2026-07-06)** : colonne de gauche réorganisée en deux sections
repliables — **Federation** (peers de confiance, masquée s'il n'y en a
aucun) et **{nom du peer local ou "Resources"}** (l'existant, liste des
`schema.table`, dépliée par défaut).

Le lien de chaque peer dans la section Federation ne pointe pas
naïvement vers son frontend — `AuthService.federationNavUrl(peer)` /
l'équivalent Svelte construit une URL de délégation directement sur
l'**API du peer cible** (`${peer.url}/auth/login?peer=<mon propre
HO_PEER_ID>&return_to=...`), exactement comme si on avait cliqué "Sign in
via" sur sa page de login — sans avoir besoin d'y passer. Ça n'a été
rendu possible que par le passage au lookup par uuid (item sur
l'identité des peers, `identite_federee.md` §4bis) : ce projet connaît
son propre `HO_PEER_ID` (exposé via `/auth/peers` → `local_id`), qui est
précisément la valeur sous laquelle le peer cible l'a enregistré — pas
besoin de savoir sous quel nom le peer cible nous connaît. Détails dans
`docs/internals/federation-protocol.md#cross-site-navigation-federationnavurl`.

Repli : si le peer cible n'a pas de `frontend_url` enregistré (n'a jamais
configuré `HO_FRONTEND_URL`), le lien pointe simplement sur son URL d'API
brute (pas de page conviviale possible sans ça).

## 21. Amélioration — UI admin : remplacer le split 45%/reste (Roles/Peers) par un mécanisme de déploiement

**Constat** : la colonne Roles/Peers de l'admin (`_ho_admin.py`, ajoutée
cette session) utilise un `max-h-[45%]` fixe pour Roles et le reste pour
Peers, empilés dans la même colonne. Remplacer par un vrai mécanisme
d'expansion/repli (accordéon ou section repliable) plutôt qu'un
pourcentage figé, pour que chaque section puisse occuper l'espace
disponible selon le nombre d'éléments plutôt qu'une proportion arbitraire.

## 22. Amélioration — rôle `connected_<peer>` pour distinguer identités locales et fédérées

**Demande** : introduire un rôle dynamique/système `connected_<peer>` (ex.
`connected_blog_demo`) attribué à une identité venue par délégation depuis
ce peer, en plus de `connected`. Objectif : permettre à `CRUD_ACCESS` de
différencier les droits d'un utilisateur local de ceux d'un utilisateur
fédéré-in, au lieu de tout traiter uniformément sous `connected`. À
préciser : où ce rôle est attribué (`federation_callback` au moment de
l'upsert dans `half_orm_meta.identity.user`, probablement), et s'il doit
être un rôle "système" par peer (créé automatiquement à l'enregistrement
d'un peer) ou une convention de nommage simple sans entrée dans
`half_orm_meta.api.role`.
