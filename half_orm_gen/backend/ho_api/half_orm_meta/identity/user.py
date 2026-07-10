"""half_orm_meta.identity.user — federated user identity.

Hand-maintained (not generated — half_orm_meta tables never get a
generated per-table module in an end-user project, see
half_orm_dev/modules.py's guards). Registered against a Model instance by
half_orm_meta.register_all(model), after which model.get_relation_class(...)
and model.classes() both return this class (half_orm.relation_factory
checks the model's own class registry before building a generic one).
"""

from half_orm.model import register_class

#: (schema, table) — the single source of truth for "this is the identity
#: user resource", used wherever code needs to recognize it generically
#: (FK-target detection in the frontend generators, the reconcile_catalog
#: sync, etc.) instead of a duplicated literal tuple.
RESOURCE = ('half_orm_meta.identity', 'user')

#: Never exposed over the API regardless of what CRUD_ACCESS an admin
#: configures — read generically by runtime.py the same way it reads a
#: generated business module's API_EXCLUDED_FIELDS.
API_EXCLUDED_FIELDS = ['password_hash']

#: Read-only over the generic CRUD API: no POST/PUT/DELETE handlers are
#: registered for this resource (writes happen through the local-auth /
#: federation login flows instead — see ho_api/local_auth.py,
#: ho_api/federation.py). Read generically by runtime.py.
READ_ONLY = True


def build_class(model):
    """Build and register the User relation class for this model instance."""
    base = model.get_relation_class('"half_orm_meta.identity"."user"')

    class User(base):
        pass

    return register_class(User)
