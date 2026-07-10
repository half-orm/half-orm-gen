"""half_orm_meta.api.field_access_out — which fields a role's access can read."""

from half_orm.model import register_class


def build_class(model):
    base = model.get_relation_class('"half_orm_meta.api".field_access_out')

    class FieldAccessOut(base):
        @classmethod
        async def list_for(cls, access_id) -> list:
            rows = await cls(access_id=access_id).ho_aselect('field_name')
            return [r['field_name'] for r in rows]

        @classmethod
        async def add(cls, access_id, field_name: str) -> None:
            await cls(access_id=access_id, field_name=field_name).ho_ainsert()

        @classmethod
        async def add_batch(cls, access_id, field_names: list) -> None:
            for field_name in field_names:
                await cls(access_id=access_id, field_name=field_name).ho_ainsert()

        @classmethod
        async def remove(cls, access_id, field_name: str) -> bool:
            result = await cls(access_id=access_id, field_name=field_name).ho_adelete('*')
            return bool(result)

    return register_class(FieldAccessOut)
