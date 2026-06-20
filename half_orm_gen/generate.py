"""
Litestar API generator for halfORM projects.

Orchestrates generation of api/app.py by combining:
- @api_* decorated route handlers  (api_routes.py)
- Auto-CRUD handlers from CRUD_ACCESS  (crud_routes.py)
- Scaffolding of missing api/ files  (scaffold.py)
"""

import os
from pathlib import Path
from typing import Iterable, Tuple, Type

from half_orm.relation import Relation

from half_orm_gen import templates as T
from half_orm_gen.scaffold import scaffold_api_dir
from half_orm_gen.api_routes import generate_api_routes
from half_orm_gen.crud_routes import generate_crud_routes


class GenApi:
    """
    Generate ``api/app.py`` from a halfORM project.

    Parameters
    ----------
    repo:
        A ``half_orm_dev.repo.Repo`` instance.  When *None*, supply
        *relation_classes*, *module_name*, and *base_dir* directly.
    relation_classes:
        Iterable of ``(RelationClass, relation_type)`` pairs (used when
        *repo* is *None*).
    module_name:
        Top-level Python package name of the halfORM model (e.g. ``"mydb"``).
    base_dir:
        Root directory of the project (``api/`` is created inside it).
    api_version:
        Integer API version (written as ``/vN/`` prefix in routes).
    """

    def __init__(
        self,
        repo=None,
        *,
        relation_classes: Iterable[Tuple[Type[Relation], str]] | None = None,
        module_name: str | None = None,
        base_dir: str | None = None,
        api_version: int | None = None,
        framework: str = 'litestar',
    ):
        if repo is not None:
            self._module_name = repo.name
            self._base_dir = Path(repo.base_dir)
            self._classes = list(repo.model.classes())
        else:
            if relation_classes is None or module_name is None or base_dir is None:
                raise ValueError(
                    "Provide either a repo or (relation_classes, module_name, base_dir)."
                )
            self._module_name = module_name
            self._base_dir = Path(base_dir)
            self._classes = list(relation_classes)

        self._api_version = api_version
        self._framework = framework
        self._api_dir = self._base_dir / 'api'
        self._generate()

    def _generate(self) -> None:
        os.environ.setdefault('API_GEN_MODE', '1')

        if self._framework == 'fastapi':
            from half_orm_gen import templates_fastapi as templates
            api_blocks, api_handlers, covered = [], [], set()
        else:
            templates = T
            api_blocks, api_handlers, covered = generate_api_routes(
                self._classes, self._api_version
            )

        # --- auto-CRUD routes ---
        crud_blocks, crud_handlers = generate_crud_routes(
            self._classes, self._api_version, covered, templates=templates
        )

        # --- assemble app.py ---
        openapi_config = (
            templates.OPENAPI_CONFIG.format(
                title=self._module_name,
                version=f'v{self._api_version}',
            )
            if self._api_version is not None
            else ''
        )

        output = (
            templates.HEADER.format(module=self._module_name)
            + (templates.CRUD_HELPERS if crud_blocks else '')
            + ''.join(api_blocks)
            + ''.join(crud_blocks)
        )

        if self._framework == 'fastapi':
            output += templates.FOOTER.format(openapi_config=openapi_config)
        else:
            route_handlers_str = ', '.join(api_handlers + crud_handlers)
            output += templates.FOOTER.format(
                route_handlers=route_handlers_str,
                openapi_config=openapi_config,
            )
            # --- scaffold missing api/ files ---
            print(f'\nScaffolding {self._api_dir} ...')
            scaffold_api_dir(self._api_dir)

        # --- write app.py ---
        self._api_dir.mkdir(parents=True, exist_ok=True)
        app_py = self._api_dir / 'app.py'
        app_py.write_text(output, encoding='utf-8')
        print(f'\nGenerated {app_py}')
