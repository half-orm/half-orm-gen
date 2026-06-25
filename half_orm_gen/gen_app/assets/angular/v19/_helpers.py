from half_orm_gen.crud_routes import _py_type_str


def _cname(schema_name: str, table_name: str) -> str:
    """PascalCase — BlogAuthor"""
    schema_name = schema_name.replace('.', '_')
    return ''.join(p.capitalize() for p in f'{schema_name}_{table_name}'.split('_'))


def _selector(schema_name: str, table_name: str, suffix: str) -> str:
    """app-blog-author-list"""
    schema_name = schema_name.replace('.', '_')
    slug = f'{schema_name}_{table_name}'.replace('_', '-')
    return f'app-{slug}-{suffix}'


def _title(schema_name: str, table_name: str) -> str:
    return f'{schema_name}.{table_name}'


def _field_type_category(field_obj) -> str:
    """Map Python type to validation category: date, datetime, number, or string."""
    py_type = _py_type_str(field_obj.py_type)
    if py_type == 'datetime.date':
        return 'date'
    if py_type == 'datetime.datetime':
        return 'datetime'
    if py_type in ('int', 'float', 'decimal.Decimal'):
        return 'number'
    return 'string'


def _store_import_path(schema_name: str, table_name: str, depth: int) -> str:
    prefix = '../' * depth
    return f"{prefix}stores/{schema_name}_{table_name}.store"


def _core_path(depth: int) -> str:
    return '../' * depth + 'core'
