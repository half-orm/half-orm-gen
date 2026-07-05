"""
API generator for halfORM projects.

Scaffolds ho_api/ and boots dynamic runtime (Litestar or FastAPI).
Also ensures the "half_orm_meta.api" schema exists in the database.
"""

import os
from pathlib import Path


def _ensure_ho_api_schema(model) -> None:
    """Create the "half_orm_meta.api"/"half_orm_meta.identity" schemas and seed system roles + catalog."""
    import asyncio
    from half_orm_gen.backend.ho_api.ddl import HO_API_DDL, HO_IDENTITY_DDL
    from half_orm_gen.backend.ho_api.loader import ensure_system_roles, reconcile_catalog
    model.execute_query(HO_API_DDL)
    model.execute_query(HO_IDENTITY_DDL)
    model.reconnect(reload=True)

    async def _run():
        await model.aconnect()
        await ensure_system_roles(model)
        await reconcile_catalog(model)

    asyncio.run(_run())
    print('  ensured  "half_orm_meta.api" schema')
    print('  ensured  "half_orm_meta.identity" schema')


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
    federation:
        When True (Litestar only), scaffold an RS256 keypair instead of
        the default HS256 shared secret, for projects that will register
        with a federation of trusted peers (see
        ``planning/identite_federee.md``). Ignored for FastAPI, which has
        no auth scaffolding at all yet.
    """

    def __init__(
        self,
        repo=None,
        *,
        module_name: str | None = None,
        base_dir: str | None = None,
        api_version: int | None = None,
        framework: str = 'litestar',
        federation: bool = False,
    ):
        self._model = repo.model if repo is not None else None
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
        self._federation = federation
        self._api_dir = self._base_dir / 'ho_api'
        self._generate()

    def _generate(self) -> None:
        os.environ.setdefault('API_GEN_MODE', '1')
        if self._model is not None:
            _ensure_ho_api_schema(self._model)
        framework_label = f' ({self._framework})' if self._framework != 'litestar' else ''
        print(f'\nScaffolding {self._api_dir}{framework_label} ...')
        if self._framework == 'fastapi':
            from half_orm_gen.backend.fastapi.v0.scaffold import scaffold_api_dir
            runtime_mod = 'half_orm_gen.backend.fastapi.v0.runtime'
            scaffold_api_dir(
                self._api_dir,
                module_name=self._module_name,
                api_version=self._api_version,
            )
        else:
            from half_orm_gen.backend.litestar.v2.scaffold import scaffold_api_dir
            runtime_mod = 'half_orm_gen.backend.litestar.v2.runtime'
            scaffold_api_dir(
                self._api_dir,
                module_name=self._module_name,
                api_version=self._api_version,
                federation=self._federation,
            )
        print(f'\nDone. Routes are loaded dynamically at startup via {runtime_mod}.')
