"""
half_orm_meta/* — hand-maintained Relation subclasses for half_orm_gen's own
internal "half_orm_meta.api" / "half_orm_meta.identity" schemas.

Mirrors the tree half_orm_dev generates for business tables (one module per
table/view, arranged by schema) — but is NOT generated. half_orm_meta tables
never get a generated per-table module in an end-user's own project (see
half_orm_dev/modules.py's guards); this tree lives inside half_orm_gen
itself instead, hand-written, so each table still gets to own the
operations performed on it.

A Model instance is built dynamically per-project (there is no fixed MODEL
singleton to decorate classes against at import time, unlike a generated
project's own package). register_all(model) must therefore be called once,
early, for a given model — after that, model.get_relation_class(...) and
model.classes() both transparently return these classes instead of a
generic dynamically-built one (half_orm.relation_factory.factory checks the
model's own class registry first).
"""

from .identity import user as _user, peer as _peer, login_state as _login_state
from .api import (
    resource as _resource, route as _route, field as _field,
    role as _role, access as _access,
    field_access_in as _field_access_in, field_access_out as _field_access_out,
    field_access_fk_auto as _field_access_fk_auto,
    field_access_searchable as _field_access_searchable,
    filter as _filter, access_filter as _access_filter, user_role as _user_role,
)

# Order matters for the ones with FK dependencies on each other: role before
# access (access.role_name references role.name), and resource before
# route/field (both reference resource(schemaname, relname)) — registration
# order itself doesn't touch the DB, but keeping it matches the DDL's own
# dependency order for readability.
_MODULES = (
    _user, _peer, _login_state,
    _resource, _role, _route, _field, _access,
    _field_access_in, _field_access_out, _field_access_fk_auto,
    _field_access_searchable, _filter, _access_filter, _user_role,
)

_registered: set = set()


def register_all(model) -> None:
    """Register every half_orm_meta.* class against `model`. Idempotent per
    model instance (a second call is a no-op) — safe to call from more than
    one entry point (e.g. both build_crud_app and generate.py's one-shot
    scaffolding) without churning duplicate class objects.
    """
    if id(model) in _registered:
        return
    for module in _MODULES:
        module.build_class(model)
    _registered.add(id(model))
