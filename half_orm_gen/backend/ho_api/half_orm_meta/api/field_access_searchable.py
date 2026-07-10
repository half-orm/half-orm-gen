"""half_orm_meta.api.field_access_searchable — which fields feed FK-select/global search."""

from half_orm.model import register_class


def build_class(model):
    base = model.get_relation_class('"half_orm_meta.api".field_access_searchable')

    class FieldAccessSearchable(base):
        @classmethod
        async def list_for(cls, access_id) -> list:
            return await cls(access_id=access_id).ho_aselect('field_name', 'role_name')

        @classmethod
        async def add(cls, access_id, field_name: str, role_name: str | None = None) -> None:
            kwargs = {'access_id': access_id, 'field_name': field_name}
            if role_name is not None:
                kwargs['role_name'] = role_name
            await cls(**kwargs).ho_ainsert()

        @classmethod
        async def remove(cls, access_id, field_name: str) -> bool:
            result = await cls(access_id=access_id, field_name=field_name).ho_adelete('*')
            return bool(result)

    return register_class(FieldAccessSearchable)
