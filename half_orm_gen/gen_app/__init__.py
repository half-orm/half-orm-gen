"""
Frontend application scaffold generator for halfORM/Litestar projects.
"""

from pathlib import Path


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
        classes = list(repo.model.classes())
        generator.generate(classes, api_version, output_dir)
