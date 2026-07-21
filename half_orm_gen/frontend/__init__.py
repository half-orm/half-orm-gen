"""
Frontend generators for halfORM projects.
"""

from pathlib import Path
from half_orm_gen.frontend.base import StoreGenerator


class GenApp:
    """
    Generate a throwaway frontend application from CRUD_ACCESS introspection.

    Parameters
    ----------
    ctx:
        A :class:`~half_orm_gen.backend.ho_api.context.HalfOrmContext`
        pairing the business model with the model that owns
        "half_orm_meta.api"/"half_orm_meta.identity".
    generator:
        A framework-specific generator instance (e.g. SvelteAppGenerator).
    output_dir:
        Directory where the application will be written.
    api_version:
        Integer API version (used to build route prefixes).
    """

    def __init__(self, *, ctx, generator, output_dir: Path, api_version=None):
        from half_orm_gen.backend.generate import _ensure_ho_api_schema
        _ensure_ho_api_schema(ctx)
        classes = list(ctx.classes())
        generator.generate(classes, api_version, output_dir, meta_model=ctx.meta_model)


class GenStore:
    """
    Generate frontend stores from CRUD_ACCESS introspection.

    Parameters
    ----------
    ctx:
        A :class:`~half_orm_gen.backend.ho_api.context.HalfOrmContext`
        pairing the business model with the model that owns
        "half_orm_meta.api"/"half_orm_meta.identity".
    generator:
        A :class:`StoreGenerator` subclass instance (e.g. SvelteGenerator).
    output_dir:
        Directory where the generated files will be written.
    api_version:
        Integer API version (used to build route prefixes).
    """

    def __init__(
        self,
        *,
        ctx,
        generator: StoreGenerator,
        output_dir: Path,
        api_version: int | None = None,
    ):
        from half_orm_gen.backend.generate import _ensure_ho_api_schema
        _ensure_ho_api_schema(ctx)
        classes = list(ctx.classes())
        generator.generate(classes, api_version, output_dir, meta_model=ctx.meta_model)
