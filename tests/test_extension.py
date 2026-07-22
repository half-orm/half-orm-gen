"""
Tests for half-orm-gen: CLI precedence (--database/--meta-database vs
half-orm-dev auto-discovery), HalfOrmContext, api_dir scaffolding, and the
@tools.api_* decorators.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import click
import pytest
from click.testing import CliRunner

from half_orm_gen.cli_extension import add_commands
from half_orm_gen.backend.ho_api.context import HalfOrmContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cli():
    """Return a Click group with the gen extension registered."""

    @click.group()
    def cli():
        pass

    with patch('half_orm_gen.cli_extension.create_and_register_extension') as mock_reg:
        def _fake_register(main_group, module):
            def decorator(func):
                group = click.group(
                    name='gen',
                    help='Generate a Litestar API and frontend backoffice from a halfORM project.',
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
    repo.database = Mock()
    repo.model = Mock(name='business_model')
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
# CLI precedence tests — half-orm-dev auto-discovery vs --database override
# ---------------------------------------------------------------------------

class TestCLIPrecedence:

    def setup_method(self):
        self.runner = CliRunner()
        self.cli = _make_cli()

    def test_gen_group_registered(self):
        assert 'gen' in self.cli.commands

    def test_api_command_exists(self):
        gen = self.cli.commands['gen']
        assert 'api' in gen.commands

    def test_api_no_flags_uses_repo_discovery(self):
        """No --database/--meta-database + half-orm-dev project found: same
        behavior as before these options existed."""
        repo = _make_mock_repo(name='mydb')
        with _mock_half_orm_dev(repo):
            with patch('half_orm_gen.cli_extension.GenApi') as mock_genapi:
                result = self.runner.invoke(self.cli, ['gen', 'api', '--litestar'])
        assert result.exit_code == 0, result.output
        assert mock_genapi.call_count == 1
        _, kwargs = mock_genapi.call_args
        assert kwargs['module_name'] == 'mydb'
        assert kwargs['ctx'].business_model is repo.model
        assert kwargs['ctx'].meta_model is repo.model  # unsplit

    def test_api_no_half_orm_dev_and_no_database_fails(self):
        """Unchanged existing error path: half_orm_dev absent, no --database given."""
        with patch.dict('sys.modules', {'half_orm_dev': None, 'half_orm_dev.repo': None}):
            result = self.runner.invoke(self.cli, ['gen', 'api', '--litestar'])
        assert result.exit_code != 0
        assert 'half_orm_dev is not installed' in result.output

    def test_api_repo_init_failure(self):
        """Unchanged existing error path: Repo() raises."""
        mock_module = Mock()
        mock_module.Repo = Mock(side_effect=Exception('no .half_orm_cli found'))
        with patch.dict('sys.modules', {
            'half_orm_dev': Mock(),
            'half_orm_dev.repo': mock_module,
        }):
            result = self.runner.invoke(self.cli, ['gen', 'api', '--litestar'])
        assert result.exit_code != 0

    def test_api_database_flag_skips_repo_discovery(self, tmp_path, monkeypatch):
        """--database alone must work with no half_orm_dev installed at all."""
        monkeypatch.chdir(tmp_path)
        fake_model = Mock(name='standalone_model')
        with patch.dict('sys.modules', {'half_orm_dev': None, 'half_orm_dev.repo': None}):
            with patch('half_orm_gen.cli_extension._ensure_standalone_model', return_value=fake_model) as mock_ensure:
                with patch('half_orm_gen.cli_extension.GenApi') as mock_genapi:
                    result = self.runner.invoke(
                        self.cli, ['gen', 'api', '--litestar', '--database', 'mydb']
                    )
        assert result.exit_code == 0, result.output
        mock_ensure.assert_called_once_with('mydb', 'mydb', tmp_path)
        _, kwargs = mock_genapi.call_args
        assert kwargs['module_name'] == 'mydb'
        assert kwargs['ctx'].business_model is fake_model
        assert kwargs['ctx'].meta_model is fake_model  # unsplit

    def test_api_database_inside_project_overrides_discovery(self, tmp_path, monkeypatch):
        """--database given while inside a half-orm-dev project fully
        overrides the business side — Repo() is never even consulted."""
        monkeypatch.chdir(tmp_path)
        fake_model = Mock(name='standalone_model')
        repo = _make_mock_repo(name='mydb')
        with _mock_half_orm_dev(repo):
            with patch('half_orm_gen.cli_extension._ensure_standalone_model', return_value=fake_model):
                with patch('half_orm_gen.cli_extension.GenApi'):
                    result = self.runner.invoke(
                        self.cli, ['gen', 'api', '--litestar', '--database', 'otherdb']
                    )
        assert result.exit_code == 0, result.output

    def test_meta_database_layers_onto_project_discovery(self, tmp_path):
        """--meta-database alone works inside an existing half-orm-dev
        project, splitting off the metadata database."""
        repo = _make_mock_repo(name='mydb', base_dir=str(tmp_path))
        fake_meta_model = Mock(name='meta_model')
        with _mock_half_orm_dev(repo):
            with patch('half_orm_gen.cli_extension._ensure_standalone_model', return_value=fake_meta_model) as mock_ensure:
                with patch('half_orm_gen.cli_extension.GenApi') as mock_genapi:
                    result = self.runner.invoke(
                        self.cli, ['gen', 'api', '--litestar', '--meta-database', 'metadb']
                    )
        assert result.exit_code == 0, result.output
        mock_ensure.assert_called_once_with('metadb', 'metadb', tmp_path)
        _, kwargs = mock_genapi.call_args
        ctx = kwargs['ctx']
        assert ctx.business_model is repo.model
        assert ctx.meta_model is fake_meta_model
        assert ctx.split is True

    def test_frontend_command_exists(self):
        gen = self.cli.commands['gen']
        assert 'frontend' in gen.commands


# ---------------------------------------------------------------------------
# HalfOrmContext
# ---------------------------------------------------------------------------

class _FakeModel:
    """Minimal stand-in for half_orm.model.Model."""

    def __init__(self, classes=(), ho_meta=None):
        self._classes = list(classes)
        self._ho_meta = ho_meta or {}
        self.aconnect_calls = 0

    def classes(self):
        yield from self._classes

    def ho_meta(self) -> dict:
        return dict(self._ho_meta)

    async def aconnect(self):
        self.aconnect_calls += 1


class TestHalfOrmContext:

    def test_defaults_meta_to_business(self):
        model = _FakeModel()
        ctx = HalfOrmContext(model)
        assert ctx.meta_model is model
        assert ctx.split is False

    def test_split_true_for_distinct_models(self):
        business = _FakeModel()
        meta = _FakeModel()
        ctx = HalfOrmContext(business, meta)
        assert ctx.split is True

    def test_classes_unsplit_is_pure_passthrough(self):
        class A: _t_fqrn = ('db', 'public', 'a')
        business = _FakeModel(classes=[(A, 'table')])
        ctx = HalfOrmContext(business)
        assert list(ctx.classes()) == [(A, 'table')]

    def test_classes_split_merges_and_dedupes(self):
        class A: _t_fqrn = ('db', 'public', 'a')
        class B: _t_fqrn = ('db', 'public', 'b')
        business = _FakeModel(classes=[(A, 'table')])
        meta = _FakeModel(classes=[(A, 'table'), (B, 'table')])
        ctx = HalfOrmContext(business, meta)
        result = list(ctx.classes())
        assert result == [(A, 'table'), (B, 'table')]  # A not duplicated

    def test_classes_split_dedupes_by_resource_not_class_identity(self):
        """Two DISTINCT class objects sharing (schema, table) — e.g. two
        half_orm_meta.* classes built by the same build_class() function
        against different models, so they'd share __module__/__qualname__
        too — must still be deduped as the same resource."""
        class A1: _t_fqrn = ('db1', 'half_orm_meta.identity', 'user')
        class A2: _t_fqrn = ('db2', 'half_orm_meta.identity', 'user')
        business = _FakeModel(classes=[(A1, 'table')])
        meta = _FakeModel(classes=[(A2, 'table')])
        ctx = HalfOrmContext(business, meta)
        result = list(ctx.classes())
        assert result == [(A1, 'table')]  # meta's A2 dropped as a duplicate resource

    def test_ho_meta_split_merges(self):
        business = _FakeModel(ho_meta={'public/foo': {'schema': 'public', 'table': 'foo'}})
        meta = _FakeModel(ho_meta={'half_orm_meta.identity/user': {'schema': 'half_orm_meta.identity', 'table': 'user'}})
        ctx = HalfOrmContext(business, meta)
        merged = ctx.ho_meta()
        assert 'public/foo' in merged
        assert 'half_orm_meta.identity/user' in merged

    def test_ho_meta_unsplit_is_passthrough(self):
        business = _FakeModel(ho_meta={'public/foo': {}})
        ctx = HalfOrmContext(business)
        assert ctx.ho_meta() == {'public/foo': {}}

    @pytest.mark.asyncio
    async def test_aconnect_all_unsplit_connects_once(self):
        business = _FakeModel()
        ctx = HalfOrmContext(business)
        await ctx.aconnect_all()
        assert business.aconnect_calls == 1

    @pytest.mark.asyncio
    async def test_aconnect_all_split_connects_both(self):
        business = _FakeModel()
        meta = _FakeModel()
        ctx = HalfOrmContext(business, meta)
        await ctx.aconnect_all()
        assert business.aconnect_calls == 1
        assert meta.aconnect_calls == 1


# ---------------------------------------------------------------------------
# ho_api/ scaffolding (half_orm_gen.backend.litestar.v2.scaffold)
# ---------------------------------------------------------------------------

class TestScaffoldApiDir:

    def test_creates_all_expected_files(self, tmp_path):
        from half_orm_gen.backend.litestar.v2.scaffold import scaffold_api_dir

        api_dir = tmp_path / 'ho_api'
        scaffold_api_dir(api_dir, module_name='mydb', api_version=0)

        assert (api_dir / 'app.py').exists()
        assert (api_dir / 'authorization.py').exists()
        assert (api_dir / 'local_auth.py').exists()
        assert (api_dir / '.env.example').exists()
        assert (api_dir / '.env').exists()
        assert (api_dir / 'custom' / 'middlewares' / 'jwt_config.py').exists()
        assert (api_dir / 'custom' / 'local_auth.py.example').exists()

    def test_app_py_imports_module_name(self, tmp_path):
        from half_orm_gen.backend.litestar.v2.scaffold import scaffold_api_dir

        api_dir = tmp_path / 'ho_api'
        scaffold_api_dir(api_dir, module_name='mydb', api_version=0)

        content = (api_dir / 'app.py').read_text()
        assert 'from mydb import MODEL' in content
        assert 'HalfOrmContext(MODEL, None)' in content
        assert 'build_crud_app(\n    _ctx,' in content

    def test_app_py_split_meta_database(self, tmp_path):
        from half_orm_gen.backend.litestar.v2.scaffold import scaffold_api_dir

        api_dir = tmp_path / 'ho_api'
        scaffold_api_dir(api_dir, module_name='mydb', meta_module_name='mymeta', api_version=0)

        content = (api_dir / 'app.py').read_text()
        assert 'from mydb import MODEL' in content
        assert 'from mymeta import MODEL as META_MODEL' in content
        assert 'HalfOrmContext(MODEL, META_MODEL)' in content

    def test_does_not_overwrite_env(self, tmp_path):
        from half_orm_gen.backend.litestar.v2.scaffold import scaffold_api_dir

        api_dir = tmp_path / 'ho_api'
        scaffold_api_dir(api_dir, module_name='mydb', api_version=0)
        original_env = (api_dir / '.env').read_text()

        scaffold_api_dir(api_dir, module_name='mydb', api_version=0)

        assert (api_dir / '.env').read_text() == original_env

    def test_app_py_always_regenerated(self, tmp_path):
        from half_orm_gen.backend.litestar.v2.scaffold import scaffold_api_dir

        api_dir = tmp_path / 'ho_api'
        api_dir.mkdir()
        (api_dir / 'app.py').write_text('# stale content')

        scaffold_api_dir(api_dir, module_name='mydb', api_version=0)

        assert (api_dir / 'app.py').read_text() != '# stale content'

    def test_federation_scaffolds_keypair(self, tmp_path):
        from half_orm_gen.backend.litestar.v2.scaffold import scaffold_api_dir

        api_dir = tmp_path / 'ho_api'
        scaffold_api_dir(api_dir, module_name='mydb', api_version=0, federation=True)

        assert (api_dir / 'federation.py').exists()
        assert (api_dir / 'private_key.pem').exists()
        assert (api_dir / 'public_key.pem').exists()
        assert 'HO_JWT_ALGORITHM=RS256' in (api_dir / '.env').read_text()


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


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
