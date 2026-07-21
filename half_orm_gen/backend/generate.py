"""
API generator for halfORM projects.

Scaffolds ho_api/ and boots the dynamic Litestar runtime.
Also ensures the "half_orm_meta.api" schema exists in the database.
"""

import os
from pathlib import Path


def _ensure_ho_api_schema(ctx) -> None:
    """Create the "half_orm_meta.api"/"half_orm_meta.identity" schemas and seed
    system roles + catalog. DDL and registration run against ctx.meta_model
    only — the business database is never written to here, so it can be
    read-only."""
    import asyncio
    from half_orm_gen.backend.ho_api import half_orm_meta
    from half_orm_gen.backend.ho_api.ddl import HO_API_DDL, HO_IDENTITY_DDL
    from half_orm_gen.backend.ho_api.loader import ensure_system_roles, reconcile_catalog
    ctx.meta_model.execute_query(HO_API_DDL)
    ctx.meta_model.execute_query(HO_IDENTITY_DDL)
    ctx.meta_model.reconnect(reload=True)
    half_orm_meta.register_all(ctx.meta_model)

    async def _run():
        await ctx.aconnect_all()
        await ensure_system_roles(ctx.meta_model)
        await reconcile_catalog(ctx)

    asyncio.run(_run())
    print('  ensured  "half_orm_meta.api" schema')
    print('  ensured  "half_orm_meta.identity" schema')


class GenApi:
    """
    Scaffold ``ho_api/`` for a halfORM project (Litestar backend).

    Parameters
    ----------
    ctx:
        A :class:`~half_orm_gen.backend.ho_api.context.HalfOrmContext`
        pairing the business model with the model that owns
        "half_orm_meta.api"/"half_orm_meta.identity".
    module_name:
        Top-level Python package name of the halfORM business model
        (e.g. ``"mydb"``).
    base_dir:
        Root directory of the project (``ho_api/`` is created inside it).
    meta_module_name:
        Top-level Python package name of the metadata model, when it's a
        separate database from the business one (``ctx.split``). ``None``
        when meta and business share the same database.
    api_version:
        Integer API version (written as ``/vN/`` prefix in routes).
    federation:
        When True, scaffold an RS256 keypair instead of the default HS256
        shared secret, for projects that will register with a federation
        of trusted peers (see ``planning/identite_federee.md``).
    """

    def __init__(
        self,
        *,
        ctx,
        module_name: str,
        base_dir,
        meta_module_name: str | None = None,
        api_version: int | None = None,
        federation: bool = False,
    ):
        self._ctx = ctx
        self._module_name = module_name
        self._meta_module_name = meta_module_name
        self._base_dir = Path(base_dir)
        self._api_version = api_version
        self._federation = federation
        self._api_dir = self._base_dir / 'ho_api'
        self._generate()

    def _generate(self) -> None:
        os.environ.setdefault('API_GEN_MODE', '1')
        _ensure_ho_api_schema(self._ctx)
        print(f'\nScaffolding {self._api_dir} ...')
        from half_orm_gen.backend.litestar.v2.scaffold import scaffold_api_dir
        scaffold_api_dir(
            self._api_dir,
            module_name=self._module_name,
            meta_module_name=self._meta_module_name,
            api_version=self._api_version,
            federation=self._federation,
        )
        print(
            '\nDone. Routes are loaded dynamically at startup via '
            'half_orm_gen.backend.litestar.v2.runtime.'
        )
