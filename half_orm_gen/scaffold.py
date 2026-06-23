"""
Scaffolding helpers for half-orm-litestar.

Creates missing api/ files on first generate. Never overwrites existing files.
"""

import shutil
from pathlib import Path

_SCAFFOLDING_DIR = Path(__file__).parent / 'scaffolding'


def scaffold_api_dir(api_dir: Path, module_name: str = '', api_version: int | None = None) -> None:
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

    # Scaffold app.py from template (substituting module_name and api_version)
    app_py = api_dir / 'app.py'
    if not app_py.exists():
        template = (_SCAFFOLDING_DIR / 'app.py').read_text(encoding='utf-8')
        version_str = str(api_version) if api_version is not None else 'None'
        content = template.replace('{module_name}', module_name).replace('{api_version}', version_str)
        app_py.write_text(content, encoding='utf-8')
        print(f'  created  {app_py}')
    else:
        print(f'  exists   {app_py}')
