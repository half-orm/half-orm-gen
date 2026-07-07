# Identité fédérée entre plusieurs bases de données (silos)

## Contexte

Objectif : permettre à half-orm-gen de fonctionner dans un scénario où
**plusieurs bases de données indépendantes** (chacune sa propre API générée,
son propre schéma métier — un "silo") **partagent les mêmes utilisateurs**.

Ce sujet est parti de l'item 13 de `a_resoudre.md` (`connected_user` ne
devrait être proposable que pour une FK ciblant la ressource "user") : pour
restreindre cette option dans l'Admin UI, il faut d'abord savoir "quelle est
LA ressource utilisateur" — et cette question devient bien plus intéressante
dès qu'on admet que les utilisateurs peuvent être partagés entre plusieurs
bases.

## Idée rejetée : source maîtresse + répliques

Première piste explorée : une BD/table `users` fait autorité, les autres
silos en gardent une réplique locale (via réplication logique Postgres ou
autre), avec l'UUID (immuable) comme seule donnée vraiment nécessaire — un
UUID absent de la réplique signifiant un utilisateur supprimé à la source.

**Rejetée** : ce modèle crée une asymétrie structurelle entre UN silo
"maître" et les autres "répliques" — alors qu'aucun silo ne devrait être
architecturalement privilégié par rapport aux autres.

## Vision retenue : fédération plate, sans maître

Séparer strictement deux préoccupations qui étaient mélangées dans l'idée
précédente :

### 1. Identité — preuve cryptographique, pas de lookup local

Un utilisateur est son UUID (immuable), attesté par un **JWT signé**.
N'importe quel silo peut vérifier la validité d'un token (signature,
expiration) **sans interroger de table `users`** — ni la sienne, ni celle
d'un autre silo. Le token *est* la preuve d'identité.

**Attention à ne pas retomber dans le centralisme** : il ne doit pas y
avoir d'"autorité d'émission" unique et privilégiée par construction. Dans
les faits, une asymétrie peut exister (tel silo émet effectivement plus de
tokens que tel autre) — mais ça reste un fait d'usage, pas une hiérarchie
architecturale. N'importe quel silo peut être émetteur pour ses propres
utilisateurs.

Le partage d'identité entre deux silos n'est donc **jamais implicite** :
silo B ne fait confiance aux tokens émis par silo A que si cette confiance
a été **explicitement accordée** (silo B maintient sa propre liste de
silos/émetteurs de confiance — clé de vérification acceptée — plutôt que
de faire confiance par défaut à quiconque). C'est une relation de pair à
pair, potentiellement multiple (un silo peut faire confiance à plusieurs
autres, ou à aucun), configurée explicitement de chaque côté receveur —
jamais un défaut du système.

**Confiance bilatérale (décidé le 2026-07-05)** : B doit avoir une entrée
pour A dans sa table `silo` pour lui faire confiance, ET A doit avoir une
entrée pour B (avec son URL) pour accepter de le rediriger — chacun
enregistre l'autre.

Raison concrète : sans ça, A recevrait un `redirect_uri` fourni par B dans
l'URL de la requête (étape 3 du protocole, section 4) et redirigerait
aveuglément vers cette adresse — **avec le token signé attestant
l'identité de la personne** (étape 6). Un attaquant pourrait alors
construire lui-même un lien `${siloA.url}/auth/login?redirect_uri=https://site-malveillant.example/vol&state=xxx` ;
si la victime a déjà une session active sur A (SSO), A la redirigerait
silencieusement vers ce site avec un JWT valide attestant sa vraie
identité — pas un simple open-redirect bénin, mais une **exfiltration
d'une preuve d'identité cryptographiquement valide**, rejouable ensuite
pour usurper la victime auprès de tout autre silo faisant confiance à A.
Exactement le risque qu'OAuth2/OIDC couvrent en exigeant une validation
stricte de `redirect_uri` contre une liste d'URLs pré-enregistrées côté
serveur d'autorisation — le rôle que joue ici l'enregistrement bilatéral :
A ne redirige (avec le token) que vers une URL de silo qu'il connaît déjà.

### 2. Autorisation — déjà locale et fédérée par construction

"Qui a le droit de faire quoi dans CE silo" reste entièrement local à
chaque BD, et c'est déjà l'architecture actuelle : `role`, `user_role`,
`CRUD_ACCESS`, `field_access_*` vivent dans le schéma
`half_orm_meta.api` de chaque BD, indépendamment des autres silos. Pas de
changement nécessaire ici — ce qui manquait manque seulement pour
l'identité, pas l'autorisation.

### 3. Profil affiché — donnée locale, optionnelle, non-autoritaire

Un silo peut vouloir afficher un nom/email plutôt qu'un UUID brut (labels,
`formatLabel`, combobox FK `select`, etc.). Il peut donc garder une table
`users` locale — mais celle-ci n'est qu'un **cache d'affichage
dénormalisé**, jamais une dépendance pour l'authentification ou
l'autorisation. Si l'utilisateur n'y figure pas encore (jamais vu par ce
silo), on affiche l'UUID brut en attendant, sans que ça bloque quoi que ce
soit.

### 4. Délégation d'authentification — pas d'orchestrateur séparé

Pas besoin d'une entité tierce dédiée à "l'identification des personnes" :
l'orchestration est distribuée, portée par la table `silo` elle-même.
`silo.url` **est l'URL de l'API CRUD** générée par half-orm-gen pour ce
pair (pas un service séparé) — chaque silo expose déjà nativement un
`/auth/login`.

Flux retenu : quand une personne se présente sur le `/auth/login` d'un
silo qui ne la reconnaît pas localement, ce silo **redirige le navigateur**
vers le `/auth/login` d'un pair de confiance (`${silo.url}/auth/login`),
qui authentifie directement et renvoie un token signé au retour. Choix
délibéré face à l'alternative "relais serveur à serveur" (le silo local
retransmettrait lui-même les identifiants) : la redirection navigateur
évite que les identifiants d'un compte transitent par un silo qui n'est
pas le sien — plus proche du modèle OIDC/SAML classique, pour plus de
sécurité.

**Protocole concret (2026-07-05, inspiré d'OAuth2/OIDC "Authorization
Code")** :

Qui choisit le pair ? La personne, explicitement — la page `/auth/login`
de B affiche "Se connecter via : [Silo A] [Silo C] …" en plus d'un
éventuel compte local. Pas de routage automatique par domaine d'email ou
autre heuristique.

1. La personne clique "Se connecter via Silo A" sur B.
2. B génère un `state` — aléatoire, imprévisible, usage unique — stocké
   **côté serveur** (courte durée de vie, ex. 5-10 min) avec : quel pair
   était visé (A), et où revenir après coup (l'URL demandée à l'origine).
3. B redirige le navigateur vers
   `${siloA.url}/auth/login?redirect_uri=${B_callback}&state=${state}`.
4. La personne s'authentifie **sur le domaine de A** — ses identifiants ne
   touchent jamais B. Si son navigateur a déjà une session valide sur A
   (cookie de session existant), A la reconnaît silencieusement et
   enchaîne directement à l'étape suivante sans rien redemander — effet
   single sign-on : se connecter sur B revient alors à un simple aller-
   retour transparent, pas une reconnexion.
5. A signe un JWT (RS256/ES256, sa clé privée) attestant l'identité
   (`sub`=UUID, `iss`=A).
6. A redirige vers `${redirect_uri}?token=${jwt}&state=${state}` (state
   réémis tel quel).
7. La route de callback de B (`/auth/callback`) : retrouve le `state` en
   base, vérifie qu'il existe, n'est pas expiré, **pas déjà consommé**
   (usage unique — invalidé immédiatement), vérifie la signature du JWT
   avec la clé publique du pair *précisément visé par ce state* (pas
   "n'importe quel pair de confiance"), crée/retrouve la ligne `user`
   locale (`origin_silo_id` = A), **émet son propre token de session
   local** (ne réutilise pas celui de A pour la suite), puis redirige vers
   l'URL de retour d'origine.

**Précision d'implémentation (2026-07-06)** : `${silo.url}/auth/login` est
l'URL de l'**API** (backend), pas du frontend SPA — et cette API n'a
elle-même aucune UI de login (le formulaire vit dans le frontend, en
`POST /auth/login` JSON). Étape 4 ci-dessus ("la personne s'authentifie
sur le domaine de A") a donc besoin d'un relais explicite : quand
`GET /auth/login` de A reçoit `redirect_uri`+`state` (i.e. A est
sollicité comme *source* d'identité par un autre pair, pas comme
demandeur), il redirige le navigateur vers `HO_FRONTEND_URL/auth/delegate`
(nouvelle variable d'env, pendant de `HO_PEER_URL` mais pour le frontend),
en repassant `redirect_uri`+`state` en query params. La page
`/auth/delegate` du frontend affiche le formulaire de login ordinaire ;
une fois authentifiée (`POST /auth/login` réussi), elle redirige
elle-même le navigateur vers `${redirect_uri}?token=...&state=...` — sans
étape de signature séparée, puisqu'un token de login local émis avec
`HO_JWT_ALGORITHM=RS256` est déjà signé avec la clé privée de ce projet,
la même dont le pendant public est enregistré chez les pairs de
confiance. Pas de vrai SSO transparent pour l'instant (pas de session
cookie inter-onglets) : si la personne n'est pas déjà connectée dans ce
même onglet sur A, elle doit ressaisir ses identifiants à chaque
délégation — amélioration possible plus tard, pas bloquante pour la démo.

**Piège rencontré (2026-07-05)** : `HO_PEER_URL`/`silo.url` doivent inclure
le préfixe de version de l'API (`/v0` par défaut, voir `gen api` dans
`cli_extension.py`) — toutes les routes, y compris celles de
`federation.py`, sont montées dessous. Un `HO_PEER_URL=http://host:8000`
sans `/v0` fait 404 sur la redirection cross-peer (`GET /auth/login`
résolu à la racine au lieu de `/v0/auth/login`). `HO_FRONTEND_URL`, lui,
ne prend pas de préfixe (ce n'est pas une route API versionnée).

**Sécurité** :
- Le `state` est LA protection anti-CSRF — sans lui, un attaquant pourrait
  forcer une victime à compléter un flux de login initié par lui.
- Vérifier la signature contre la clé du pair **spécifiquement ciblé par
  ce state**, pas "un pair de confiance quelconque" — sinon un pair
  malveillant pourrait substituer son propre token.
- Le token de A ne sert qu'à cette poignée de main ; B émet ensuite son
  propre token de session, pour ne pas coupler la durée de vie des
  sessions des deux silos.
- **HTTPS obligatoire** sur tous les échanges (redirections, callback) —
  sauf en mode développement local. Les paramètres d'URL (token, state)
  ne doivent jamais transiter en clair sur un réseau non chiffré.

### 4bis. Enregistrement des peers — carte auto-descriptive (2026-07-06)

**Problème identifié en implémentant la navigation inter-sites (item 20,
`a_resoudre.md`)** : `peer.name` est aujourd'hui un label choisi librement
par l'admin qui enregistre — rien ne garantit qu'un pair s'appelle
partout de la même façon. Ça rend la navigation "aller sur B" fragile :
pour construire `${B}/auth/login?peer=<X>` depuis A de façon à ce que B
délègue bien vers A, il faudrait connaître le nom sous lequel *B* a
enregistré *A* — une donnée que A ne connaît pas et ne maîtrise pas.

**Décision** : découpler le label cosmétique de la clé d'identification
réelle, exactement comme `user.id` (immuable) vs `user.name` (affichage) :

- Nouvel identifiant stable **`HO_PEER_ID`** (uuid), généré une fois au
  scaffold `--federation`, à côté de la paire de clés — l'auto-identifiant
  de ce projet, jamais recalculé.
- Nouvelle variable **`HO_PEER_NAME`** — le nom que ce projet se donne à
  lui-même. Le nom voyage désormais *avec* l'enregistrement plutôt que
  d'être ressaisi par chaque admin qui enregistre ce pair : plus de
  divergence possible entre silos.
- `peer.name` reste stocké (affichage dans l'UI, boutons "Sign in via …")
  mais n'est plus jamais **saisi** localement — uniquement reçu du pair
  distant au moment de l'enregistrement.
- Le lookup de délégation (`auth_login`, cas "requesting") se fait
  désormais par `id` (uuid), plus par `name`.

**Enregistrement simplifié — carte auto-descriptive** : au lieu de
saisir séparément nom/URL/uuid/clé publique, chaque peer expose un blob
encodé unique regroupant tout :

```json
{ "id": "<HO_PEER_ID>", "name": "<HO_PEER_NAME>", "url": "<HO_PEER_URL>",
  "frontend_url": "<HO_FRONTEND_URL>", "jwt_public_key": "-----BEGIN PUBLIC KEY-----..." }
```

Encodage retenu : **simple `base64(JSON)`, sans signature**. La confiance
ne vient pas d'une vérification cryptographique de ce blob (il n'y en a
pas — il faudrait le vérifier avec la clé qu'il contient lui-même, ce qui
ne prouve rien de plus que "cohérent avec soi-même") mais du canal par
lequel l'admin transmet la carte à l'autre admin — exactement le même
modèle de confiance que le copier-coller manuel de la clé publique
aujourd'hui, juste groupé en un seul geste.

- `GET /ho_admin/peer/self` renvoie en plus un champ `export_key` (le
  blob prêt à copier). L'UI admin remplace l'affichage séparé
  url/algorithm/public_key par un bouton "Copy registration key".
- `POST /ho_admin/peer` n'accepte plus name/url/jwt_public_key séparés —
  un seul champ `registration_key` (le blob collé), décodé et validé
  côté serveur ; l'admin qui enregistre ne choisit ni le nom ni l'uuid,
  seulement `trusted` (vrai par défaut — coller la clé EST la décision
  de confiance).

**Enregistrement non symétrique** : coller la carte de B chez A ne fait
rien chez B — chaque enregistrement est un geste unilatéral, indépendant,
sans poignée de main. Implication concrète pour la navigation (item 20) :
arriver sur B et pouvoir s'y signer via A suppose que B a *aussi*
enregistré la carte de A, pas seulement l'inverse — cohérent avec la
contrainte bilatérale déjà connue du protocole de délégation (aucun des
deux sens n'est automatique).

**Correction (2026-07-06)** : la prémisse initiale supposait implicitement
que le copier-coller se fait par le même admin dans deux onglets — faux
en général, les deux admins peuvent être deux personnes différentes, qui
transmettent la carte par n'importe quel canal (email, chat, ...), pas
nécessairement instantané. La carte porte donc un `expires_at` (30 min
après génération) ; `/ho_admin/peer/self` régénère systématiquement une
carte fraîche à chaque appel (pas de cache), et `_decode_registration_key`
rejette toute carte expirée à la validation. Ça borne la fenêtre
d'exploitation d'une carte qui fuiterait dans un canal semi-public, sans
rien coûter à l'usage normal (regénérer = juste rouvrir la page admin).

### 5. Signature des tokens — RS256/ES256 partout, dès la génération

Aujourd'hui, `HO_JWT_SECRET` est symétrique (HMAC) : vérifier un token
implique de connaître le même secret qui a servi à le signer. Incompatible
avec la fédération — un pair capable de vérifier les tokens de silo A
pourrait alors aussi en forger en se faisant passer pour A.

**Décision (2026-07-05)** : générer systématiquement une paire de clés
asymétrique (RS256 ou ES256) pour **tout** projet, dès `half_orm gen`, pas
seulement pour ceux qui activent la fédération. Aucune base installée à
migrer à ce jour, donc pas de raison de garder deux mécanismes (HMAC pour
le mono-silo, asymétrique pour le fédéré) à maintenir indéfiniment. La
génération de la paire de clés est entièrement automatisée par l'outil,
comme `HO_JWT_SECRET` aujourd'hui — transparent pour l'utilisateur. Un
projet qui décide de fédérer plus tard n'a alors **aucune migration à
faire** : il partage sa clé publique déjà existante (`silo.jwt_public_key`
côté des pairs), point.

Coût du changement : calcul RSA/ECDSA plus lourd que HMAC, mais négligeable
pour une opération de login/vérification, pas un chemin critique en
performance.

## Emplacement (schéma) — paramétrable, `half_orm_meta.identity` par défaut

Ces deux tables vivent dans un schéma dédié, séparé de
`half_orm_meta.api` (préoccupation différente : identité/fédération, pas
contrôle d'accès CRUD). Nom **paramétrable à la génération** — une BD peut
déjà avoir sa propre table `user` métier, préexistante et incompatible ;
dans ce cas elle ne participe simplement pas à la fédération. Par défaut :
`half_orm_meta.identity`, cohérent avec la convention déjà établie par
`half_orm_meta.api`, reconnaissable comme faisant partie du générateur
plutôt que d'être nommé d'après un projet ou une organisation particulière.

## Schéma SQL (première ébauche, 2026-07-05)

```sql
CREATE TABLE silo (
    id             uuid PRIMARY KEY,              -- PAS de DEFAULT : c'est l'uuid AUTO-DÉCLARÉ du pair (HO_PEER_ID),
                                                   -- pas un id local — reçu via la carte d'enregistrement (§4bis)
    name           text NOT NULL,                 -- reçu du pair (HO_PEER_NAME), jamais saisi localement
    url            text NOT NULL,                 -- URL de base de l'API CRUD de ce pair (sert aussi pour /auth/login)
    frontend_url   text,                          -- URL du frontend de ce pair (navigation inter-sites, item 20)
    jwt_public_key text,                          -- clé publique RS256/ES256, pour vérifier les tokens ÉMIS PAR ce silo
    trusted        boolean NOT NULL DEFAULT true, -- révocable sans perdre l'historique
    created_at     timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "user" (
    id             uuid PRIMARY KEY,   -- PAS généré localement : vient du claim `sub` du token, immuable
    origin_silo_id uuid REFERENCES silo(id),  -- quel silo a le premier attesté cette identité (personne, pas attribut)
    name           text,               -- cache d'affichage local, optionnel
    email          text,
    password_hash  text,               -- uniquement pour un compte LOCAL à ce silo (pas d'identité fédérée) ; jamais en clair
    first_seen_at  timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at   timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

`now()` et `CURRENT_TIMESTAMP` sont strictement équivalents en PostgreSQL
(fonction `STABLE`, réévaluée à chaque transaction — jamais figée au moment
du `CREATE TABLE`) ; `CURRENT_TIMESTAMP` retenu ici pour la syntaxe SQL
standard.

`password_hash` : uniquement renseigné pour un compte créé et authentifié
localement dans ce silo (pas d'identité fédérée reçue d'un autre silo de
confiance) — jamais de mot de passe pour une identité dont l'origine est un
autre silo, l'authentification passant alors par la vérification du token
émis par ce silo d'origine.

## Conséquence sur l'item 13 (`a_resoudre.md`)

Avec cette vision, `connected_user` n'a plus forcément besoin de cibler une
vraie contrainte FK locale vers une table users — puisque le référentiel
utilisateur peut être purement externe (le token JWT), sans table
correspondante dans la BD du silo. La désignation "quelle est LA ressource
user" (piste de l'item 13) devrait donc plutôt permettre de désigner un
champ/une ressource *optionnelle*, utilisée uniquement pour l'affichage —
pas une exigence structurelle pour que `connected_user` fonctionne.

## Ouvert / à trancher plus tard

- Mécanisme concret pour qu'un silo déclare/maintienne sa liste de silos
  de confiance (quel(s) émetteur(s) accepter, quelle clé publique pour
  chacun — stockage dans `silo.jwt_public_key`, cf. section 5, mais
  l'admin UI/le flux d'ajout d'un pair reste à concevoir).
- Comment/par qui cette confiance est-elle accordée en pratique (un admin
  de silo B ajoute silo A à sa liste — mais faut-il aussi un geste
  explicite côté silo A, ou la confiance est-elle unilatérale, portée
  uniquement par le receveur) ?
- Si une personne ne correspond à AUCUN silo de confiance connu du silo
  local (pas de compte local, pas de pair capable de l'authentifier),
  comment le `/auth/login` réagit-il — refus simple, ou proposition de
  créer un compte local ?
- Si un silo choisit de garder un profil local (nom/email), comment ce
  profil se peuple-t-il la première fois qu'un UUID inconnu (mais dont le
  silo émetteur est de confiance) se connecte (à la volée depuis les
  claims du token, en tâche de fond, etc.) ?
- Lien avec l'item 13 : formaliser la désignation "ressource d'affichage
  utilisateur" (optionnelle) une fois cette vision stabilisée.
