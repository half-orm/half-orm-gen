"""half_orm_meta.api.access_filter — which named filters an access applies."""

from half_orm.model import register_class


def build_class(model):
    base = model.get_relation_class('"half_orm_meta.api".access_filter')

    class AccessFilter(base):
        @classmethod
        async def list_for(cls, access_id) -> list:
            return await cls(access_id=access_id).ho_aselect('filter_id')

        @classmethod
        async def add(cls, access_id, filter_id) -> None:
            await cls(access_id=access_id, filter_id=filter_id).ho_ainsert()

        @classmethod
        async def remove(cls, access_id, filter_id) -> bool:
            result = await cls(access_id=access_id, filter_id=filter_id).ho_adelete('*')
            return bool(result)

    return register_class(AccessFilter)
