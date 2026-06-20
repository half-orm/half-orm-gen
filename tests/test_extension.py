"""
Tests for half-orm-gen extension.
"""

import inspect
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import click
import pytest
from click.testing import CliRunner

from half_orm_gen.cli_extension import add_commands


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cli():
    """Return a Click group with the litestar extension registered."""

    @click.group()
    def cli():
        pass

    with patch('half_orm_gen.cli_extension.create_and_register_extension') as mock_reg:
        def _fake_register(main_group, module):
            def decorator(func):
                group = click.group(
                    name='litestar',
                    help='Generate and manage a Litestar API from a halfORM project.',
                )(func)
                main_group.add_command(group)
                return group
            return decorator
        mock_reg.side_effect = _fake_register
        add_commands(cli)

    return cli


def _make_mock_repo(name='testdb', base_dir='/tmp/testdb'):
    repo = Mock()
    repo.name = name
    repo.base_dir = base_dir
    return repo


def _mock_half_orm_dev(repo):
    """Context: sys.modules with a mocked half_orm_dev.repo.Repo."""
    mock_module = Mock()
    mock_module.Repo = Mock(return_value=repo)
    return patch.dict('sys.modules', {
        'half_orm_dev': Mock(),
        'half_orm_dev.repo': mock_module,
    })


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class TestCLI:

    def setup_method(self):
        self.runner = CliRunner()
        self.cli = _make_cli()

    def test_litestar_group_registered(self):
        assert 'litestar' in self.cli.commands

    def test_generate_command_exists(self):
        litestar = self.cli.commands['litestar']
        assert 'generate' in litestar.commands

    def test_litestar_help(self):
        result = self.runner.invoke(self.cli, ['litestar', '--help'])
        assert result.exit_code == 0
        assert 'generate' in result.output

    def test_generate_help(self):
        result = self.runner.invoke(self.cli, ['litestar', 'generate', '--help'])
        assert result.exit_code == 0
        assert '--dry-run' in result.output
        assert 'api/app.py' in result.output

    def test_generate_dry_run(self):
        repo = _make_mock_repo(name='mydb')
        with _mock_half_orm_dev(repo):
            with patch('half_orm_gen.generate.GenApi'):
                result = self.runner.invoke(self.cli, ['litestar', 'generate', '--dry-run'])
        assert result.exit_code == 0
        assert 'mydb' in result.output

    def test_generate_calls_genapi(self):
        repo = _make_mock_repo()
        with _mock_half_orm_dev(repo):
            with patch('half_orm_gen.generate.GenApi') as mock_genapi:
                result = self.runner.invoke(self.cli, ['litestar', 'generate'])
        assert result.exit_code == 0
        mock_genapi.assert_called_once_with(repo, api_version=0)

    def test_generate_no_half_orm_dev(self):
        """Generate should fail gracefully when half_orm_dev is not installed."""
        with patch.dict('sys.modules', {'half_orm_dev': None, 'half_orm_dev.repo': None}):
            result = self.runner.invoke(self.cli, ['litestar', 'generate'])
        assert result.exit_code != 0

    def test_generate_repo_init_failure(self):
        """Generate should fail gracefully when Repo() raises."""
        mock_module = Mock()
        mock_module.Repo = Mock(side_effect=Exception('no .half_orm_cli found'))
        with patch.dict('sys.modules', {
            'half_orm_dev': Mock(),
            'half_orm_dev.repo': mock_module,
        }):
            result = self.runner.invoke(self.cli, ['litestar', 'generate'])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# tools.py — decorator tests
# ---------------------------------------------------------------------------

class TestTools:

    def _import_tools(self):
        from half_orm_gen import tools
        return tools

    def test_api_get_marks_route(self):
        tools = self._import_tools()

        @tools.api_get('/items/{id: uuid}')
        async def handler(self, request): pass

        assert handler.is_api_route is True
        assert handler.http_method == 'GET'

    def test_api_post_http_method(self):
        tools = self._import_tools()

        @tools.api_post('/items')
        async def handler(self): pass

        assert handler.http_method == 'POST'

    def test_api_put_http_method(self):
        tools = self._import_tools()

        @tools.api_put('/items/{id: uuid}')
        async def handler(self): pass

        assert handler.http_method == 'PUT'

    def test_api_patch_http_method(self):
        tools = self._import_tools()

        @tools.api_patch('/items/{id: uuid}')
        async def handler(self): pass

        assert handler.http_method == 'PATCH'

    def test_api_delete_http_method(self):
        tools = self._import_tools()

        @tools.api_delete('/items/{id: uuid}')
        async def handler(self): pass

        assert handler.http_method == 'DELETE'

    def test_path_stored_in_litestar_params(self):
        tools = self._import_tools()

        @tools.api_get('/user/{id: uuid}')
        async def handler(self): pass

        assert handler.litestar_params['path'] == '/user/{id: uuid}'

    def test_guards_stored_in_litestar_params(self):
        tools = self._import_tools()

        @tools.api_get('/items', guards=['connected', 'has_user_access'])
        async def handler(self): pass

        assert handler.litestar_params['guards'] == ['connected', 'has_user_access']

    def test_wraps_preserves_name_and_doc(self):
        tools = self._import_tools()

        @tools.api_get('/items')
        async def my_handler(self):
            """My docstring."""
            pass

        assert my_handler.__name__ == 'my_handler'
        assert my_handler.__doc__ == 'My docstring.'

    def test_metadata_stores_signature(self):
        tools = self._import_tools()
        import uuid as _uuid

        @tools.api_get('/items/{id: uuid}')
        async def handler(self, id: '_uuid.UUID', q: 'str' = None): pass

        sig = handler.metadata['signature']
        assert 'id' in sig.parameters
        assert 'q' in sig.parameters

    def test_metadata_stores_documentation(self):
        tools = self._import_tools()

        @tools.api_get('/items')
        async def handler(self):
            """A useful description."""
            pass

        assert handler.metadata['documentation'] == 'A useful description.'

    def test_callable_after_decoration(self):
        """The decorated function must still be callable."""
        tools = self._import_tools()

        @tools.api_get('/items')
        async def handler(self):
            return 42

        import asyncio
        result = asyncio.run(handler(None))
        assert result == 42


# ---------------------------------------------------------------------------
# scaffolding tests
# ---------------------------------------------------------------------------

class TestScaffolding:

    def test_creates_all_expected_files(self, tmp_path):
        from half_orm_gen.scaffold import scaffold_api_dir as _scaffold_api_dir

        api_dir = tmp_path / 'api'
        api_dir.mkdir()
        _scaffold_api_dir(api_dir)

        assert (api_dir / '__init__.py').exists()
        assert (api_dir / 'guards.py').exists()
        assert (api_dir / 'custom' / 'routes.py').exists()
        assert (api_dir / 'custom' / '__init__.py').exists()
        assert (api_dir / 'custom' / 'middlewares' / '__init__.py').exists()
        assert (api_dir / 'custom' / 'middlewares' / 'authorization.py').exists()

    def test_guards_py_contains_public_and_connected(self, tmp_path):
        from half_orm_gen.scaffold import scaffold_api_dir as _scaffold_api_dir

        api_dir = tmp_path / 'api'
        api_dir.mkdir()
        _scaffold_api_dir(api_dir)

        content = (api_dir / 'guards.py').read_text()
        assert 'async def public' in content
        assert 'async def connected' in content

    def test_does_not_overwrite_existing_files(self, tmp_path):
        from half_orm_gen.scaffold import scaffold_api_dir as _scaffold_api_dir

        api_dir = tmp_path / 'api'
        api_dir.mkdir()

        # Pre-existing user content
        guards_py = api_dir / 'guards.py'
        guards_py.write_text('# my custom guards')

        _scaffold_api_dir(api_dir)

        assert guards_py.read_text() == '# my custom guards'

    def test_partial_scaffold_fills_missing_only(self, tmp_path):
        from half_orm_gen.scaffold import scaffold_api_dir as _scaffold_api_dir

        api_dir = tmp_path / 'api'
        api_dir.mkdir()
        (api_dir / 'guards.py').write_text('# existing')

        _scaffold_api_dir(api_dir)

        # guards.py untouched, but other files created
        assert (api_dir / 'guards.py').read_text() == '# existing'
        assert (api_dir / 'custom' / 'routes.py').exists()


# ---------------------------------------------------------------------------
# GenApi helper method tests
# ---------------------------------------------------------------------------

class TestGenApiHelpers:
    """Unit tests for route-generation helpers (api_routes module)."""

    def setup_method(self):
        from half_orm_gen.api_routes import (
            _path_params, _query_params, _format_litestar_args,
            _extract_guards,
        )
        self._path_params = _path_params
        self._query_params = _query_params
        self._format_litestar_args = _format_litestar_args
        self._extract_guards = _extract_guards

    def test_path_params_single(self):
        assert self._path_params('/items/{id: uuid}') == 'id: Any'

    def test_path_params_multiple(self):
        result = self._path_params('/post/{post_id: uuid}/user/{user_id: uuid}')
        assert 'post_id: Any' in result
        assert 'user_id: Any' in result

    def test_path_params_none(self):
        assert self._path_params('/items') == ''

    def test_query_params_skips_self(self):
        sig = inspect.signature(lambda self, x: None)
        decl, call = self._query_params(sig)
        assert 'self' not in decl
        assert 'self' not in call
        assert 'x' in decl
        assert 'x' in call

    def test_query_params_with_annotation_and_default(self):
        def fn(self, name: str, limit: int = 10): pass

        sig = inspect.signature(fn)
        decl, call = self._query_params(sig)
        assert 'name: str' in decl
        assert 'limit: int=10' in decl
        assert call == 'name, limit'

    def test_format_litestar_args_path(self):
        result = self._format_litestar_args({'path': '/user/{id: uuid}'}, [], '', None)
        assert '"/user/{id: uuid}"' in result

    def test_format_litestar_args_path_with_version(self):
        result = self._format_litestar_args({'path': '/user/{id: uuid}'}, [], '', 1)
        assert '"/v1/user/{id: uuid}"' in result

    def test_format_litestar_args_guards(self):
        result = self._format_litestar_args({'path': '/items'}, ['public', 'connected'], '', None)
        assert 'guards=[guards.public, guards.connected]' in result

    def test_format_litestar_args_description(self):
        result = self._format_litestar_args({'path': '/items'}, [], 'My description.', None)
        assert 'My description.' in result

    def test_extract_guards_string_list(self):
        assert self._extract_guards({'guards': ['public', 'connected']}) == ['public', 'connected']

    def test_extract_guards_callable_list(self):
        def public(): pass
        def connected(): pass

        assert self._extract_guards({'guards': [public, connected]}) == ['public', 'connected']

    def test_extract_guards_empty(self):
        assert self._extract_guards({}) == []
        assert self._extract_guards({'guards': None}) == []


# ---------------------------------------------------------------------------
# GenApi integration test (mocked relations + tmp filesystem)
# ---------------------------------------------------------------------------

class TestGenApi:

    def _make_relation(self, module_str, class_name, schemaname, methods):
        """Build a minimal mock Relation class with @api_* decorated methods."""
        attrs = {
            '__module__': module_str,
            '__name__': class_name,
            '_schemaname': schemaname,
            '_dbname': module_str.split('.')[0],
            '_ho_dataclass_name': classmethod(lambda cls: f'DC_{class_name}'),
        }
        attrs.update(methods)
        return type(class_name, (), attrs)

    def test_generate_creates_app_py(self, tmp_path):
        from half_orm_gen.generate import GenApi
        from half_orm_gen import tools

        @tools.api_get('/users', guards=['public'])
        async def get_users(self): pass

        relation = self._make_relation(
            'mydb.actor.user', 'User', 'actor',
            {'get_users': get_users},
        )

        with patch('importlib.import_module', return_value=Mock(spec=[])):
            GenApi(
                relation_classes=[(relation, 'table')],
                module_name='mydb',
                base_dir=str(tmp_path),
            )

        assert (tmp_path / 'api' / 'app.py').exists()

    def test_generated_app_py_contains_route(self, tmp_path):
        from half_orm_gen.generate import GenApi
        from half_orm_gen import tools

        @tools.api_get('/users', guards=['public'])
        async def get_users(self): pass

        relation = self._make_relation(
            'mydb.actor.user', 'User', 'actor',
            {'get_users': get_users},
        )

        with patch('importlib.import_module', return_value=Mock(spec=[])):
            GenApi(
                relation_classes=[(relation, 'table')],
                module_name='mydb',
                base_dir=str(tmp_path),
            )

        content = (tmp_path / 'api' / 'app.py').read_text()
        assert '@get' in content
        assert '"/users"' in content
        assert 'mydb_actor_user_get_users' in content

    def test_generated_app_py_has_header(self, tmp_path):
        from half_orm_gen.generate import GenApi

        with patch('importlib.import_module', return_value=Mock(spec=[])):
            GenApi(
                relation_classes=[],
                module_name='mydb',
                base_dir=str(tmp_path),
            )

        content = (tmp_path / 'api' / 'app.py').read_text()
        assert 'from mydb import ho_baseclasses' in content
        assert 'application = Litestar(' in content

    def test_generate_scaffolds_missing_api_files(self, tmp_path):
        from half_orm_gen.generate import GenApi

        with patch('importlib.import_module', return_value=Mock(spec=[])):
            GenApi(
                relation_classes=[],
                module_name='mydb',
                base_dir=str(tmp_path),
            )

        assert (tmp_path / 'api' / 'guards.py').exists()
        assert (tmp_path / 'api' / 'custom' / 'routes.py').exists()

    def test_generate_does_not_overwrite_guards(self, tmp_path):
        from half_orm_gen.generate import GenApi

        api_dir = tmp_path / 'api'
        api_dir.mkdir()
        guards_py = api_dir / 'guards.py'
        guards_py.write_text('# project-specific guards')

        with patch('importlib.import_module', return_value=Mock(spec=[])):
            GenApi(
                relation_classes=[],
                module_name='mydb',
                base_dir=str(tmp_path),
            )

        assert guards_py.read_text() == '# project-specific guards'

    def test_generate_overwrites_app_py(self, tmp_path):
        """app.py is always regenerated, even if it already exists."""
        from half_orm_gen.generate import GenApi

        api_dir = tmp_path / 'api'
        api_dir.mkdir()
        app_py = api_dir / 'app.py'
        app_py.write_text('# old content')

        with patch('importlib.import_module', return_value=Mock(spec=[])):
            GenApi(
                relation_classes=[],
                module_name='mydb',
                base_dir=str(tmp_path),
            )

        assert app_py.read_text() != '# old content'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])