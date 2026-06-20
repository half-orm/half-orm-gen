"""
Scaffolding helpers for half-orm-litestar.

Creates missing api/ files on first generate. Never overwrites existing files.
"""

import shutil
from pathlib import Path

_SCAFFOLDING_DIR = Path(__file__).parent / 'scaffolding'


def scaffold_api_dir(api_dir: Path) -> None:
    """Create missing api/ scaffolding files. Never overwrites existing files."""
    files = {
        api_dir / 'guards.py':
            _SCAFFOLDING_DIR / 'guards.py',
        api_dir / '__init__.py':
            _SCAFFOLDING_DIR / 'api_init.py',
        api_dir / 'custom' / 'routes.py':
            _SCAFFOLDING_DIR / 'custom_routes.py',
        api_dir / 'custom' / '__init__.py':
            _SCAFFOLDING_DIR / 'custom_init.py',
        api_dir / 'custom' / 'middlewares' / '__init__.py':
            _SCAFFOLDING_DIR / 'custom_middlewares_init.py',
        api_dir / 'custom' / 'middlewares' / 'authorization.py':
            _SCAFFOLDING_DIR / 'custom_authorization.py',
        api_dir / 'roles' / 'core.py':
            _SCAFFOLDING_DIR / 'roles_core.py',
    }
    for dest, src in files.items():
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, dest)
            print(f'  created  {dest}')
        else:
            print(f'  exists   {dest}')
