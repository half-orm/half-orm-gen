"""
CLI extension for half-orm-gen.

Registers the ``gen`` sub-command group under the ``half_orm`` CLI::

    half_orm gen api
    half_orm gen frontend
"""

import sys
from pathlib import Path
import click
from half_orm.cli_utils import create_and_register_extension
from half_orm_gen.gen_app import GenApp
from half_orm_gen.generate import GenApi
from half_orm_gen.gen_app.svelte import SvelteAppGenerator
from half_orm_gen.gen_app.angular import AngularAppGenerator

_VERSION_FILE = Path('api') / '.api_version'


def _read_api_version() -> int:
    try:
        return int(_VERSION_FILE.read_text().strip())
    except (FileNotFoundError, ValueError):
        return 0


def _write_api_version(version: int) -> None:
    _VERSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    _VERSION_FILE.write_text(str(version) + '\n')


def add_commands(main_group):
    """Required entry point for halfORM extensions."""

    @create_and_register_extension(main_group, sys.modules[__name__])
    def gen():
        """Generate a Litestar API and frontend backoffice from a halfORM project."""
        pass

    @gen.command('api')
    @click.option(
        '--dry-run', is_flag=True, default=False,
        help='Print what would be generated without writing any file.',
    )
    @click.option(
        '--bump', is_flag=True, default=False,
        help='Bump the API version to N+1 (asks for confirmation).',
    )
    @click.option('--litestar', 'framework', flag_value='litestar',
                  help='Generate a Litestar app.')
    @click.option('--fastapi', 'framework', flag_value='fastapi',
                  help='Generate a FastAPI app (no @api_* support).')
    def api(dry_run, bump, framework):
        """Generate api/app.py from CRUD_ACCESS and @api_* decorated methods.

        The API version is read from api/.api_version (default: 0).
        Use --bump to move to N+1; the new value is saved for future runs.
        To revert a mistaken bump: git checkout api/.api_version.

        Must be run from inside a half-orm-dev project directory.
        On first run, missing scaffolding files (guards.py, custom/) are
        created automatically and are never overwritten on subsequent runs.
        """
        try:
            from half_orm_dev.repo import Repo
        except ImportError:
            click.echo(
                'Error: half_orm_dev is not installed. '
                'Install it with: pip install half-orm-dev',
                err=True,
            )
            sys.exit(1)

        try:
            repo = Repo()
        except Exception as exc:
            click.echo(
                f'Error: could not load the halfORM project ({exc}).\n'
                'Make sure you are inside a half-orm-dev project directory.',
                err=True,
            )
            sys.exit(1)

        if not framework:
            click.echo('Error: specify --litestar or --fastapi.', err=True)
            sys.exit(1)

        api_version = _read_api_version()

        if bump:
            next_version = api_version + 1
            click.confirm(
                f'Bump API version from v{api_version} to v{next_version}?',
                abort=True,
            )
            _write_api_version(next_version)
            api_version = next_version

        if dry_run:
            click.echo(
                f'[dry-run] would generate api/app.py ({framework}) for project: {repo.name}'
                f' (v{api_version})'
            )
            return

        click.echo(f'Generating {framework} API for project: {repo.name} (v{api_version})')
        GenApi(repo, api_version=api_version, framework=framework)
        if framework == 'litestar':
            click.echo('\nTo run:  litestar --app api.app:application run --reload')
        else:
            click.echo('\nTo run:  uvicorn api.app:application --reload')

    @gen.command('frontend')
    @click.option('--svelte',   'framework', flag_value='svelte',
                  help='Generate a SvelteKit 5 application.')
    @click.option('--angular',  'framework', flag_value='angular',
                  help='Generate an Angular 22 application (signal-based).')
    @click.option('--output', default=None,
                  help='Output directory (default: frontend/<framework>).')
    def frontend(framework, output):
        """Generate a frontend backoffice from CRUD_ACCESS introspection.

        Produces a complete SvelteKit or Angular application with Tailwind CSS,
        per-resource List/CreateForm/DetailView components in generated/,
        admin-only route pages, and a minimal JWT login.

        Must be run from inside a half-orm-dev project directory.
        """
        try:
            from half_orm_dev.repo import Repo
        except ImportError:
            click.echo(
                'Error: half_orm_dev is not installed. '
                'Install it with: pip install half-orm-dev',
                err=True,
            )
            sys.exit(1)

        try:
            repo = Repo()
        except Exception as exc:
            click.echo(
                f'Error: could not load the halfORM project ({exc}).\n'
                'Make sure you are inside a half-orm-dev project directory.',
                err=True,
            )
            sys.exit(1)

        api_version = _read_api_version()
        output_dir = Path(output) if output else Path('frontend') / framework

        if not framework:
            click.echo('Error: specify --svelte or --angular.', err=True)
            sys.exit(1)
        if framework == 'svelte':
            generator = SvelteAppGenerator()
        elif framework == 'angular':
            generator = AngularAppGenerator()
        else:
            click.echo(f'Error: unknown framework "{framework}".', err=True)
            sys.exit(1)

        click.echo(f'Generating {framework} application → {output_dir}')
        GenApp(repo, generator=generator, output_dir=output_dir, api_version=api_version)
        if framework == 'svelte':
            click.echo(f'\nTo run:  cd {output_dir} && npm install && npm run dev')
        elif framework == 'angular':
            click.echo(f'\nTo run:  cd {output_dir} && npm install && npm start')
