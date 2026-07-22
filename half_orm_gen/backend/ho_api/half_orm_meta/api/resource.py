"""half_orm_meta.api.resource — catalog of relations the API is aware of."""

from half_orm.model import register_class


def build_class(model):
    base = model.get_relation_class('"half_orm_meta.api".resource')

    class Resource(base):
        @classmethod
        async def sync(cls, live_relations: dict[tuple[str, str], bool]) -> None:
            """Insert a resource row for any live relation not already tracked.

            live_relations maps (schema, table) -> is_association (the
            auto-detected pivot-shape default, see loader.reconcile_catalog).
            Only used for the INITIAL is_association value on INSERT — never
            touched again on subsequent calls, so an admin override (see
            set_is_association) survives every later reconcile/restart.

            Never deletes or flags anything: Route.sync is what flags a
            relation as gone (deprecated=True on its routes) — resource
            rows are kept so a deprecated relation's past routes/fields
            still reference a valid resource(schemaname, relname).
            """
            db_resources = {
                (r['schemaname'], r['relname']) for r in await cls().ho_aselect()
            }
            for schema, table in set(live_relations) - db_resources:
                await cls(
                    schemaname=schema, relname=table,
                    is_association=live_relations[(schema, table)],
                ).ho_ainsert()

        @classmethod
        async def list_all(cls) -> list:
            """Return [{schemaname, relname, is_association}, ...] for every tracked resource."""
            return await cls().ho_aselect('schemaname', 'relname', 'is_association')

        @classmethod
        async def set_is_association(cls, schema: str, table: str, value: bool) -> bool:
            """Admin override — persists across every later reconcile (see sync)."""
            result = await cls(schemaname=schema, relname=table).ho_aupdate(is_association=value)
            return bool(result)

    return register_class(Resource)
