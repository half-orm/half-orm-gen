from half_orm_gen.frontend.base import _cname, _title, _field_type_category


def _selector(schema_name: str, table_name: str, suffix: str) -> str:
    """app-blog-author-list"""
    schema_name = schema_name.replace('.', '_')
    slug = f'{schema_name}_{table_name}'.replace('_', '-')
    return f'app-{slug}-{suffix}'


def _store_import_path(schema_name: str, table_name: str, depth: int) -> str:
    prefix = '../' * depth
    return f"{prefix}stores/{schema_name}_{table_name}.store"


def _core_path(depth: int) -> str:
    return '../' * depth + 'core'
