"""
API generator for halfORM projects.

Scaffolds ho_api/ and boots dynamic runtime (Litestar or FastAPI).
"""

import os
from pathlib import Path

from half_orm_gen.scaffold import scaffold_api_dir


class GenApi:
    """
    Scaffold ``ho_api/`` for a halfORM project.

    Parameters
    ----------
    repo:
        A ``half_orm_dev.repo.Repo`` instance.  When *None*, supply
        *module_name* and *base_dir* directly.
    module_name:
        Top-level Python package name of the halfORM model (e.g. ``"mydb"``).
    base_dir:
        Root directory of the project (``ho_api/`` is created inside it).
    api_version:
        Integer API version (written as ``/vN/`` prefix in routes).
    framework:
        ``'litestar'`` (default) or ``'fastapi'``.
    """

    def __init__(
        self,
        repo=None,
        *,
        module_name: str | None = None,
        base_dir: str | None = None,
        api_version: int | None = None,
        framework: str = 'litestar',
    ):
        if repo is not None:
            self._module_name = repo.name
            self._base_dir = Path(repo.base_dir)
        else:
            if module_name is None or base_dir is None:
                raise ValueError(
                    "Provide either a repo or (module_name, base_dir)."
                )
            self._module_name = module_name
            self._base_dir = Path(base_dir)

        self._api_version = api_version
        self._framework = framework
        self._api_dir = self._base_dir / 'ho_api'
        self._generate()

    def _generate(self) -> None:
        os.environ.setdefault('API_GEN_MODE', '1')
        framework_label = f' ({self._framework})' if self._framework != 'litestar' else ''
        print(f'\nScaffolding {self._api_dir}{framework_label} ...')
        scaffold_api_dir(
            self._api_dir,
            module_name=self._module_name,
            api_version=self._api_version,
            framework=self._framework,
        )
        runtime_mod = (
            'half_orm_gen.runtime_fastapi'
            if self._framework == 'fastapi'
            else 'half_orm_gen.runtime'
        )
        print(f'\nDone. Routes are loaded dynamically at startup via {runtime_mod}.')
