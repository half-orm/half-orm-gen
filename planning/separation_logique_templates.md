# Séparer la logique de génération du contenu Angular/Svelte

## Contexte

Les générateurs frontend (`half_orm_gen/frontend/angular/v19/*.py`,
`half_orm_gen/frontend/svelte/v5/*.py`) produisent aujourd'hui le code
Angular/Svelte sous forme de f-strings Python, avec la logique de
décision (quels champs, quelles conditions, quels blocs optionnels) et le
gabarit du code cible (TypeScript/HTML/Svelte) entremêlés dans les mêmes
fonctions. Conséquence directe : comme Angular et Svelte utilisent tous
les deux `{{ }}` pour leur propre interpolation, chaque interpolation
littérale dans le gabarit doit être échappée en `{{{{`/`}}}}` dans la
f-string — illisible, sans coloration syntaxique, sans lint possible sur
le TS/Svelte tant qu'il n'est pas généré. C'est l'approche que
l'utilisateur qualifie de "PHP-style" (mélange logique + rendu) et qu'il
souhaite corriger avant d'ajouter la moindre nouvelle fonctionnalité aux
générateurs (cf. `.claude/plans/greedy-soaring-comet.md`, mis en pause en
attendant ce chantier).

## Décision : approche en deux phases

**Phase 1 (maintenant)** : séparer, dans chaque fichier générateur,
la logique d'assemblage (boucles sur les champs/ressources, décisions
conditionnelles, préparation des fragments) du gabarit lui-même — sans
changer de mécanisme, toujours des f-strings, mais **isolées dans des
fichiers dédiés qui ne contiennent que ça**. Les fichiers "logique"
actuels (`_list_component.py`, `_detail_component.py`,
`_form_components.py`, `_permissions_matrix.py`, `_ho_admin.py`,
`_app_shell.py`, etc.) ne gardent que : rassembler les métadonnées de la
ressource, calculer les listes/drapeaux dérivés (champs visibles, FK
groupées, etc.), appeler les fonctions de gabarit avec des valeurs déjà
résolues, assembler/écrire le résultat. Les fonctions de gabarit, elles,
ne prennent que des arguments déjà prêts (chaînes, listes de chaînes déjà
formatées) et ne contiennent ni boucle ni condition qui changerait la
*structure* du résultat — uniquement de l'interpolation de valeur.

**Phase 2 (plus tard, pas maintenant)** : une fois cette frontière propre
établie, envisager de migrer les fonctions de gabarit isolées vers de
vrais fichiers externes (`.ts`/`.svelte` réels, avec coloration
syntaxique dans l'éditeur) chargés via `Path.read_text()` et substitués
avec `string.Template` (stdlib, délimiteur `$identifiant`, aucune
dépendance ajoutée) plutôt que des f-strings Python. Choix motivé : à la
différence de Jinja2 (délimiteurs personnalisables, mais boucles/
conditions possibles *dans* le template — ce qui réinviterait la logique
côté gabarit), `string.Template` ne permet que la substitution pure, ce
qui **impose structurellement** la séparation recherchée plutôt que de
compter sur la discipline. Explicitement différé : la Phase 1 doit
d'abord clarifier les frontières fichier par fichier avant d'envisager ce
changement de mécanisme.

## Convention retenue pour la Phase 1

Pour chaque module générateur mixte, séparer en deux :
- **`_xxx.py`** (inchangé de nom, garde la logique) : calcule les
  métadonnées et fragments dérivés, appelle les fonctions de gabarit,
  assemble/écrit les fichiers de sortie.
- **fonctions de gabarit** : regroupées soit dans un fichier frère dédié
  (ex. `_xxx_templates.py`), soit — à trancher au fil de l'implémentation
  selon ce qui reste le plus lisible fichier par fichier — dans un
  sous-module `templates/` par framework. Une fonction de gabarit ne fait
  que `return f"..."` avec des paramètres déjà résolus ; aucune branche
  `if`/boucle qui déciderait quoi inclure.

## Périmètre

- **Concerné** : tous les générateurs frontend
  (`half_orm_gen/frontend/angular/v19/*.py`,
  `half_orm_gen/frontend/svelte/v5/*.py`) — c'est là que la collision
  `{{ }}` fait mal.
- **Hors périmètre pour l'instant** : les templates backend
  (`half_orm_gen/backend/litestar/v2/scaffold.py` et similaires) génèrent
  du Python à partir de Python — les f-strings n'y posent pas le même
  problème d'échappement (pas de collision de syntaxe), donc pas de
  priorité immédiate. À revisiter si le principe s'avère payant côté
  frontend.

## Convention effectivement retenue

En pratique, plutôt que des fonctions de gabarit Python isolées dans un
fichier frère (`_xxx_templates.py`), on est allés directement vers de
vrais fichiers externes (`templates/<composant>/*.html`, `*.ts`, `.json`,
etc.), chargés via `Path.read_text()` et substitués avec `string.Template`
(stdlib, `$identifiant` / `${identifiant}`). Un petit loader partagé
(`_templates.py`, fonction `_tpl(relpath)`, mis en cache) est utilisé par
tous les fichiers `_xxx.py`. Ce qui devait être la "Phase 2" a donc été
fait dès cette passe — voir le retour utilisateur explicite ayant motivé
ce choix.

Point de vigilance découvert en pratique : `$` est le caractère spécial
de `string.Template`, donc tout `$` littéral dans le rendu final (Angular
`$event`, `$any`, `$index`, ou un template-literal JS `` `${expr}` ``)
doit être échappé en `$$` dans le fichier gabarit. Une f-string mal
échappée aurait simplement produit du texte incorrect silencieusement ;
ici, une erreur de ce type lève `KeyError`/`ValueError` à la génération
(`string.Template.substitute()`), ce qui a servi de garde-fou systématique
pendant la conversion (chaque fichier reconverti a été rejoué et comparé
à l'ancien rendu f-string avant validation).

## État

**Terminé** : tous les générateurs Angular
(`half_orm_gen/frontend/angular/v19/*.py` — `_detail_component.py`,
`_list_component.py`, `_form_components.py`, `_permissions_matrix.py`,
`_ho_admin.py`, `_app_shell.py`, `_pages.py`, `_specs.py`, `_static.py`)
ne contiennent plus que de la logique d'assemblage ; tout le gabarit vit
sous `half_orm_gen/frontend/angular/v19/templates/`.

**Restant** : `half_orm_gen/frontend/svelte/v5/*.py` — même chantier, pas
encore attaqué.

## Prochaine étape

Reprendre ensuite `.claude/plans/greedy-soaring-comet.md` (matrice de
permissions éditable inline) — mis en pause, reste valide, à appliquer
une fois cette réorganisation faite (ou au fil de l'eau sur les fichiers
qu'il touchera de toute façon). Svelte reste à faire séparément, hors
scope immédiat sauf demande explicite.
