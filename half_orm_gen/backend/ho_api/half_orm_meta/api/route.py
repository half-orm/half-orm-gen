"""half_orm_meta.api.route — per-(resource, verb) existence/deprecation."""

from half_orm.model import register_class

_VERBS = ('GET', 'POST', 'PUT', 'DELETE')


def build_class(model):
    base = model.get_relation_class('"half_orm_meta.api".route')

    class Route(base):
        @classmethod
        async def list_all(cls) -> list:
            return await cls().ho_aselect()

        @classmethod
        async def sync(cls, live_relations: set) -> None:
            """Insert routes for newly-live relations; flag/unflag deprecated ones.

            A relation counts as "live" the moment it's yielded by
            model.ho_meta() — including "half_orm_meta.identity"."user" once
            with_half_orm_meta covers it, same as any business table, with
            no special-casing needed here.
            """
            db_routes = {
                (r['schema_name'], r['table_name'], r['verb']): r['deprecated']
                for r in await cls().ho_aselect()
            }
            db_relations = {(s, t) for s, t, _ in db_routes}

            for schema, table in live_relations - db_relations:
                for verb in _VERBS:
                    await cls(
                        schema_name=schema, table_name=table, verb=verb
                    ).ho_ainsert()

            for (schema, table, verb), was_deprecated in db_routes.items():
                should = (schema, table) not in live_relations
                if was_deprecated != should:
                    await cls(
                        schema_name=schema, table_name=table, verb=verb
                    ).ho_aupdate(deprecated=should)

    return register_class(Route)
