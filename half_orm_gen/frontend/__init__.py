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
    repo:
        A ``half_orm_dev.repo.Repo`` instance.
    generator:
        A framework-specific generator instance (e.g. SvelteAppGenerator).
    output_dir:
        Directory where the application will be written.
    api_version:
        Integer API version (used to build route prefixes).
    """

    def __init__(self, repo, *, generator, output_dir: Path, api_version=None):
        from half_orm_gen.backend.generate import _ensure_ho_api_schema
        _ensure_ho_api_schema(repo.model)
        classes = list(repo.model.classes())
        generator.generate(classes, api_version, output_dir, model=repo.model)


class GenStore:
    """
    Generate frontend stores from CRUD_ACCESS introspection.

    Parameters
    ----------
    repo:
        A ``half_orm_dev.repo.Repo`` instance.
    generator:
        A :class:`StoreGenerator` subclass instance (e.g. SvelteGenerator).
    output_dir:
        Directory where the generated files will be written.
    api_version:
        Integer API version (used to build route prefixes).
    """

    def __init__(
        self,
        repo,
        *,
        generator: StoreGenerator,
        output_dir: Path,
        api_version: int | None = None,
    ):
        from half_orm_gen.backend.generate import _ensure_ho_api_schema
        _ensure_ho_api_schema(repo.model)
        classes = list(repo.model.classes())
        generator.generate(classes, api_version, output_dir, model=repo.model)
