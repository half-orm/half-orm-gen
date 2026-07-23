"""
CLI extension for half-orm-gen.

Registers the ``gen`` sub-command group under the ``half_orm`` CLI::

    half_orm gen api      → ho_api/
    half_orm gen frontend → ho_frontend/<framework>/
"""

import sys
from pathlib import Path
import click
from half_orm.cli_utils import create_and_register_extension
from half_orm_gen.frontend import GenApp
from half_orm_gen.backend.generate import GenApi
from half_orm_gen.backend.ho_api.context import HalfOrmContext
from half_orm_gen.frontend.svelte.v5.svelte import SvelteAppGenerator
from half_orm_gen.frontend.angular.v19.angular import AngularAppGenerator

_VERSION_FILE = Path('ho_api') / '.api_version'

_STANDALONE_MODULE_TEMPLATE = """\
from half_orm.model import Model

MODEL = Model('{database}', with_half_orm_meta={with_half_orm_meta!r})
"""


def _read_api_version() -> int:
    try:
        return int(_VERSION_FILE.read_text().strip())
    except (FileNotFoundError, ValueError):
        return 0


def _write_api_version(version: int) -> None:
    _VERSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    _VERSION_FILE.write_text(str(version) + '\n')


def _ensure_standalone_model(
    database: str, module_name: str, base_dir: Path,
    with_half_orm_meta: bool | str = False,
):
    """Write {base_dir}/{module_name}/__init__.py once if missing (never
    overwritten — same convention as ho_api/custom/guards.py.example), then
    import it and return its MODEL.

    with_half_orm_meta must only be truthy for whichever model actually owns
    "half_orm_meta.api"/".identity" (the meta model — the business model
    itself, in single-DB mode) — never for a business model paired with a
    separate --meta-database. Otherwise, if the business database happens to
    physically carry a half_orm_meta schema (e.g. leftover from an earlier
    single-DB run), business_model.classes() would enumerate its own
    (never-registered) generic classes for it, and HalfOrmContext.classes()
    — which yields business_model first — would silently shadow meta_model's
    real hand-registered classes (half_orm_meta.identity.user's
    login/signup routes, notably) with no error, just missing routes.
    """
    pkg_dir = base_dir / module_name
    init_py = pkg_dir / '__init__.py'
    if not init_py.exists():
        pkg_dir.mkdir(parents=True, exist_ok=True)
        init_py.write_text(
            _STANDALONE_MODULE_TEMPLATE.format(
                database=database, with_half_orm_meta=with_half_orm_meta,
            ),
            encoding='utf-8',
        )
        click.echo(f'  created  {init_py}')

    sys.path.insert(0, str(base_dir))
    import importlib
    module = importlib.import_module(module_name)
    return module.MODEL


def _resolve_ctx(database: str | None, meta_database: str | None):
    """Resolve (ctx, module_name, base_dir) from --database/--meta-database,
    falling back to half-orm-dev project auto-discovery when neither
    override is given. Exits the process on any resolution failure, same
    error messages as before this option existed."""
    if database:
        module_name, base_dir = database, Path.cwd()
        is_split = bool(meta_database and meta_database != module_name)
        business_model = _ensure_standalone_model(
            database, module_name, base_dir,
            with_half_orm_meta=False if is_split else 'half_orm_meta.identity.user',
        )
    else:
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

        if repo.database is None:
            click.echo(
                'Error: no halfORM project found in this directory or any parent.\n'
                'Make sure you are inside a half-orm-dev project directory.',
                err=True,
            )
            sys.exit(1)

        module_name, base_dir, business_model = repo.name, Path(repo.base_dir), repo.model

    if meta_database and meta_database != module_name:
        meta_model = _ensure_standalone_model(
            meta_database, meta_database, base_dir,
            with_half_orm_meta='half_orm_meta.identity.user',
        )
    else:
        meta_model = None

    return HalfOrmContext(business_model, meta_model), module_name, base_dir


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
    @click.option(
        '--federation', is_flag=True, default=False,
        help='Scaffold an RS256 keypair for cross-project identity federation '
             '(Litestar only) instead of the default HS256 shared secret.',
    )
    @click.option(
        '--database', default=None, metavar='NAME',
        help='Business database (half_orm config name). Use outside a '
             'half-orm-dev project, or to override auto-discovery.',
    )
    @click.option(
        '--meta-database', default=None, metavar='NAME',
        help='Separate database owning "half_orm_meta.api"/".identity", for '
             'when the business database is read-only. Defaults to the same '
             'database as --database / the auto-discovered project.',
    )
    def api(dry_run, bump, framework, federation, database, meta_database):
        """Generate ho_api/app.py from CRUD_ACCESS and @api_* decorated methods.

        The API version is read from ho_api/.api_version (default: 0).
        Use --bump to move to N+1; the new value is saved for future runs.
        To revert a mistaken bump: git checkout ho_api/.api_version.

        Must be run from inside a half-orm-dev project directory, or pass
        --database to target any database directly.

        On first run, missing scaffolding files (guards.py, custom/) are
        created automatically and are never overwritten on subsequent runs.
        """
        ctx, module_name, base_dir = _resolve_ctx(database, meta_database)

        if not framework:
            click.echo('Error: specify --litestar.', err=True)
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
                f'[dry-run] would generate ho_api/app.py ({framework}) for project: {module_name}'
                f' (v{api_version})'
            )
            return

        click.echo(f'Generating {framework} API for project: {module_name} (v{api_version})')
        GenApi(
            ctx=ctx, module_name=module_name, base_dir=base_dir,
            meta_module_name=meta_database or None,
            api_version=api_version, federation=federation,
        )
        click.echo('\nTo run:  litestar --app ho_api.app:application run --reload')

    @gen.command('frontend')
    @click.option('--svelte',   'framework', flag_value='svelte',
                  help='Generate a SvelteKit 5 application.')
    @click.option('--angular',  'framework', flag_value='angular',
                  help='Generate an Angular 22 application (signal-based).')
    @click.option('--output', default=None,
                  help='Output directory (default: frontend/<framework>).')
    @click.option(
        '--database', default=None, metavar='NAME',
        help='Business database (half_orm config name). Use outside a '
             'half-orm-dev project, or to override auto-discovery.',
    )
    @click.option(
        '--meta-database', default=None, metavar='NAME',
        help='Separate database owning "half_orm_meta.api"/".identity", for '
             'when the business database is read-only. Defaults to the same '
             'database as --database / the auto-discovered project.',
    )
    def frontend(framework, output, database, meta_database):
        """Generate a frontend backoffice from CRUD_ACCESS introspection.

        Produces a complete SvelteKit or Angular application with Tailwind CSS,
        per-resource List/CreateForm/DetailView components in generated/,
        admin-only route pages, and a minimal JWT login.

        Must be run from inside a half-orm-dev project directory, or pass
        --database to target any database directly.
        """
        ctx, module_name, base_dir = _resolve_ctx(database, meta_database)

        api_version = _read_api_version()
        output_dir = Path(output) if output else Path('ho_frontend') / framework

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
        GenApp(ctx=ctx, generator=generator, output_dir=output_dir, api_version=api_version)
        if framework == 'svelte':
            click.echo(f'\nTo run:  cd {output_dir} && npm install && npm run dev')
        elif framework == 'angular':
            click.echo(f'\nTo run:  cd {output_dir} && npm install && npm start')
