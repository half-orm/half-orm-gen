"""
Internal registries for @ho_api_role and @ho_api_filter methods.

Decorators are defined in half_orm_gen.tools (public API).
This module holds the runtime registries and the startup discovery function.
"""

_ROLE_REGISTRY: dict[tuple[str, str, str], callable] = {}
# key: (schema, table, role_name)

_FILTER_REGISTRY: dict[tuple[str, str, str], callable] = {}
# key: (schema, table, filter_name)


def register_relation_roles(cls):
    """Scan a Relation subclass for @ho_api_role methods and register them."""
    try:
        inst = cls()
        schema = inst._t_fqrn[1]
        table  = inst._t_fqrn[2]
    except Exception:
        return
    for attr in vars(cls).values():
        role_name = getattr(attr, '_ho_api_role', None)
        if role_name:
            _ROLE_REGISTRY[(schema, table, role_name)] = attr


async def discover_and_register(model, classes) -> None:
    """Scan user modules for @ho_api_role / @ho_api_filter, populate registries and DB."""
    import importlib
    from half_orm_gen.backend.ho_api.models import HoApiModels
    api = HoApiModels(model)
    Role   = api.role()
    Filter = api.filter()
    for cls, _kind in classes:
        try:
            mod = importlib.import_module(cls.__module__)
        except ModuleNotFoundError:
            continue
        user_cls = getattr(mod, cls.__name__, cls)
        try:
            inst = user_cls()
            schema = inst._t_fqrn[1]
            table  = inst._t_fqrn[2]
        except Exception:
            continue
        for attr in vars(user_cls).values():
            role_name = getattr(attr, '_ho_api_role', None)
            if role_name:
                _ROLE_REGISTRY[(schema, table, role_name)] = attr
                if not await Role()(name=role_name).ho_aselect('name'):
                    await Role()(
                        name=role_name, deletable=True,
                        schemaname=schema, relname=table,
                    ).ho_ainsert()
            filter_name = getattr(attr, '_ho_api_filter', None)
            if filter_name:
                _FILTER_REGISTRY[(schema, table, filter_name)] = attr
                rows = await Filter()(schema_name=schema, table_name=table, name=filter_name).ho_aselect('id')
                if not rows:
                    await Filter()(schema_name=schema, table_name=table, name=filter_name).ho_ainsert()
