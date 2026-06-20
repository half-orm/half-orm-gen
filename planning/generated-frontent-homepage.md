# Plan : GitHub Pages + liens home page

## Contexte

La home page générée (`once=True`) doit servir de point de départ complet pour
le développeur. Elle doit pointer vers la documentation du projet. Or, la
documentation actuelle est minimale (un seul `docs/crud_access.md`). Il faut
donc créer la documentation GitHub Pages **en premier**, puis ajouter les
liens vers elle dans les templates de home page.

---

## Partie 1 — GitHub Pages (MkDocs)

### Choix technique

**MkDocs + Material theme** — standard Python, compatible avec l'existant
(`docs/crud_access.md` déjà rédigé, projet Python).

URL cible : `https://half-orm.github.io/half-orm-litestar/`

### Structure de documentation

```
docs/
├── index.md            ← Intro + liens vers les sections
├── quickstart.md       ← Installation + premier projet en 5 minutes
├── crud_access.md      ← (EXISTANT) Référence complète CRUD_ACCESS
├── frontend.md         ← Génération backoffice Svelte & Angular
├── cli.md              ← Référence CLI (api, frontend, --bump, etc.)
└── customization.md    ← guards.py, roles/, middlewares/
```

### Fichiers à créer

**`mkdocs.yml`** (racine du projet) :
```yaml
site_name: half-orm-litestar
site_url: https://half-orm.github.io/half-orm-litestar/
repo_url: https://github.com/half-orm/half-orm-litestar
repo_name: half-orm/half-orm-litestar

theme:
  name: material
  palette:
    primary: deep purple

nav:
  - Home: index.md
  - Quick start: quickstart.md
  - CRUD_ACCESS: crud_access.md
  - Frontend: frontend.md
  - CLI reference: cli.md
  - Customization: customization.md

plugins:
  - search
```

**`.github/workflows/docs.yml`** :
```yaml
name: Deploy docs
on:
  push:
    branches: [main]
    paths: ['docs/**', 'mkdocs.yml']
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install mkdocs-material
      - run: mkdocs gh-deploy --force
```

**`pyproject.toml`** — ajouter l'URL Documentation :
```toml
[project.urls]
Homepage      = "https://github.com/half-orm/half-orm-litestar"
Documentation = "https://half-orm.github.io/half-orm-litestar/"
```

### Contenu des docs (lignes directrices)

- `index.md` : présentation, badges (PyPI, license), liens rapides vers les 4 sections
- `quickstart.md` : `pip install`, `half_orm litestar api`, `half_orm litestar frontend`, `npm run dev` — du zéro au backoffice en 10 min
- `frontend.md` : architecture (generated/ vs developer-owned), routes ho_bo/, auth guard, once=True
- `cli.md` : toutes les options (`--litestar`, `--fastapi`, `--svelte`, `--angular`, `--bump`, `--output`)
- `customization.md` : guards, roles, middlewares — reprend le README existant

---

## Partie 2 — Liens dans la home page générée

### Liens à afficher (statiques, connus à la génération)

| Lien | URL |
|------|-----|
| halfORM Litestar docs | `https://half-orm.github.io/half-orm-litestar/` |
| GitHub repo | `https://github.com/half-orm/half-orm-litestar` |
| Svelte docs (Svelte only) | `https://svelte.dev` |
| Angular docs (Angular only) | `https://angular.dev` |
| Litestar docs | `https://litestar.dev` |

### Placement dans la home page

Section "Resources" ou "Liens utiles" en bas de la page, après les commandes :

```
[ halfORM Litestar docs ]  [ GitHub ]  [ Svelte/Angular ]  [ Litestar ]
```

Chaque lien : icône + label, style discret (`text-gray-500 hover:text-gray-800`).

### Changement de signature (conservé du plan précédent)

```python
def _home_page(first_route, resources, version_prefix, project_name) -> str:
def _home_component_ts(first_route, resources, version_prefix, project_name) -> str:
```

Les URLs des liens sont hardcodées dans les templates (constantes connues).

---

## Ordre d'exécution recommandé

1. Créer `mkdocs.yml` + `docs/*.md` (contenu minimal mais publiable)
2. Créer `.github/workflows/docs.yml`
3. Mettre à jour `pyproject.toml` (URL Documentation)
4. Implémenter la home page enrichie avec tableau ressources + liens
5. Commit + push → GitHub Pages se déploie automatiquement

---

## Fichiers touchés

- `mkdocs.yml` (nouveau)
- `docs/index.md`, `quickstart.md`, `frontend.md`, `cli.md`, `customization.md` (nouveaux)
- `.github/workflows/docs.yml` (nouveau)
- `pyproject.toml` (ajout URL Documentation)
- `half_orm_litestar/gen_app/svelte.py` (home page)
- `half_orm_litestar/gen_app/angular.py` (home component)

---

## Vérification

- `mkdocs serve` en local — vérifier les 6 pages
- Push sur main → GitHub Actions déploie
- Régénérer un frontend — vérifier les liens dans la home page
- `rm +page.svelte && half_orm litestar frontend --svelte` → once=True OK
