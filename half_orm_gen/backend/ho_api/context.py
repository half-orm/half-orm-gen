"""
Pairs the (possibly read-only) business database with the database that owns
"half_orm_meta.api"/"half_orm_meta.identity" — normally the same connection,
optionally a separate writable "proxy" database when the business database
can't be altered.
"""

from dataclasses import dataclass, field

from half_orm.model import Model


@dataclass(frozen=True)
class HalfOrmContext:
    """Two half_orm.model.Model connections joined at the Python layer.

    meta_model defaults to business_model (the single-DB case): every method
    below then degrades to a pass-through over business_model alone — no
    extra query, no extra connection.
    """

    business_model: Model
    meta_model: Model = field(default=None)  # type: ignore[assignment]

    def __post_init__(self):
        if self.meta_model is None:
            object.__setattr__(self, 'meta_model', self.business_model)

    @property
    def split(self) -> bool:
        """True when meta_model is a genuinely separate connection."""
        return self.meta_model is not self.business_model

    def model_for(self, schema: str) -> Model:
        """The model owning `schema` — meta_model for half_orm_meta.* (e.g.
        "half_orm_meta.identity", which owns "user", exposed as an ordinary
        CRUD resource), business_model otherwise. Resolving a schema/table
        string read back from the catalog (half_orm_meta.api.resource/
        route/access) must go through this rather than assuming
        business_model — half_orm_meta.identity.user lives on meta_model
        once split."""
        return self.meta_model if schema.startswith('half_orm_meta') else self.business_model

    def classes(self):
        """business_model.classes(), plus meta_model's own (allowlisted)
        relations when split, deduped by (schema, table).

        Delegates entirely to Model.classes() — which already falls back to
        get_relation_class() (pure DB introspection, no Python file
        required) for any resource with no generated/importable module, or
        whose module doesn't define the expected class.

        Deduping by (cls.__module__, cls.__qualname__) would be wrong here:
        every half_orm_meta.* class is built by the SAME build_class()
        function in half_orm_gen's own source (see half_orm_meta/__init__.py)
        — one call per model — so two distinct classes built against two
        distinct models (business_model and meta_model) share the exact
        same __module__/__qualname__ despite being different class objects
        bound to different connections; deduping on that pair silently
        fails to catch the collision, and build_crud_app then registers the
        same route path twice (ImproperlyConfiguredException at startup).
        (schema, table) — read off cls._t_fqrn[1:], set as a class
        attribute by half_orm.relation_factory's factory(), no
        instantiation needed — is what actually identifies a resource."""
        seen = set()
        for cls, kind in self.business_model.classes():
            seen.add(cls._t_fqrn[1:])
            yield cls, kind
        if self.split:
            for cls, kind in self.meta_model.classes():
                key = cls._t_fqrn[1:]
                if key not in seen:
                    yield cls, kind

    def ho_meta(self) -> dict:
        """business_model.ho_meta() merged with meta_model.ho_meta() when split."""
        merged = dict(self.business_model.ho_meta())
        if self.split:
            merged.update(self.meta_model.ho_meta())
        return merged

    async def aconnect_all(self) -> None:
        await self.business_model.aconnect()
        if self.split:
            await self.meta_model.aconnect()
