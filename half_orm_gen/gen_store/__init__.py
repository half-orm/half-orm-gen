"""
Frontend store generator for halfORM/Litestar projects.
"""

from pathlib import Path
from half_orm_gen.gen_store.base import StoreGenerator


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
        classes = list(repo.model.classes())
        generator.generate(classes, api_version, output_dir)