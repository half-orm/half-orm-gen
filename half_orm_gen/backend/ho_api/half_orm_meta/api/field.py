"""half_orm_meta.api.field — per-column existence/deprecation/label ordering."""

from half_orm.model import register_class


def build_class(model):
    base = model.get_relation_class('"half_orm_meta.api".field')

    class Field(base):
        @classmethod
        async def sync(cls, live_fields: set) -> None:
            """Insert field rows for newly-live columns; flag/unflag deprecated ones."""
            db_fields = {
                (r['schema_name'], r['table_name'], r['column_name']): r['deprecated']
                for r in await cls().ho_aselect()
            }
            for schema, table, col in live_fields - set(db_fields):
                await cls(
                    schema_name=schema, table_name=table, column_name=col
                ).ho_ainsert()

            for (schema, table, col), was_deprecated in db_fields.items():
                should = (schema, table, col) not in live_fields
                if was_deprecated != should:
                    await cls(
                        schema_name=schema, table_name=table, column_name=col
                    ).ho_aupdate(deprecated=should)

        @classmethod
        async def list_for(cls, schema: str, table: str) -> list:
            return await cls(
                schema_name=schema, table_name=table, deprecated=False
            ).ho_aselect('column_name', 'label_order')

        @classmethod
        async def with_labels(cls) -> list:
            """Rows for every field that's part of a resource's display label."""
            from half_orm.null import NULL
            return await cls(label_order=('is not', NULL)).ho_aselect(
                'schema_name', 'table_name', 'column_name', 'label_order',
            )

        @classmethod
        async def set_label(cls, schema: str, table: str, field_name: str, label_order: int) -> None:
            await cls(
                schema_name=schema, table_name=table, column_name=field_name,
            ).ho_aupdate(label_order=label_order)

        @classmethod
        async def unset_label(cls, schema: str, table: str, field_name: str) -> None:
            from half_orm.null import NULL
            await cls(
                schema_name=schema, table_name=table, column_name=field_name,
            ).ho_aupdate(label_order=NULL)

    return register_class(Field)
