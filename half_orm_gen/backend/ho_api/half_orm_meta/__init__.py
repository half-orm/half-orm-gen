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

from .identity import user as _user
from .api import resource as _resource, route as _route, field as _field

_MODULES = (_user, _resource, _route, _field)

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
