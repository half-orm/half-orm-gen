"""half_orm_meta.api.resource — catalog of relations the API is aware of."""

from half_orm.model import register_class


def build_class(model):
    base = model.get_relation_class('"half_orm_meta.api".resource')

    class Resource(base):
        @classmethod
        async def sync(cls, live_relations: set) -> None:
            """Insert a resource row for any live relation not already tracked.

            Never deletes or flags anything: Route.sync is what flags a
            relation as gone (deprecated=True on its routes) — resource
            rows are kept so a deprecated relation's past routes/fields
            still reference a valid resource(schemaname, relname).
            """
            db_resources = {
                (r['schemaname'], r['relname']) for r in await cls().ho_aselect()
            }
            for schema, table in live_relations - db_resources:
                await cls(schemaname=schema, relname=table).ho_ainsert()

    return register_class(Resource)
