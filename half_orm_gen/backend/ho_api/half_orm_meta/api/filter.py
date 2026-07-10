"""half_orm_meta.api.filter — named row filters (@ho_api_filter)."""

from half_orm.model import register_class


def build_class(model):
    base = model.get_relation_class('"half_orm_meta.api".filter')

    class Filter(base):
        @classmethod
        async def register(cls, schema: str, table: str, name: str) -> None:
            """Ensure a filter row exists (idempotent) — called when
            registry.py discovers an @ho_api_filter method."""
            rows = await cls(schema_name=schema, table_name=table, name=name).ho_aselect('id')
            if not rows:
                await cls(schema_name=schema, table_name=table, name=name).ho_ainsert()

        @classmethod
        async def list_for(cls, schema: str, table: str) -> list:
            rows = await cls(schema_name=schema, table_name=table).ho_aselect()
            return [{'id': str(r['id']), 'name': r['name']} for r in rows]

        @classmethod
        async def name_for(cls, filter_id) -> str | None:
            rows = await cls(id=filter_id).ho_aselect('name')
            return rows[0]['name'] if rows else None

    return register_class(Filter)
