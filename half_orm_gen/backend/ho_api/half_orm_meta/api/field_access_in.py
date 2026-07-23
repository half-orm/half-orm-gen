"""half_orm_meta.api.field_access_in — which fields a role's access can write."""

from half_orm.model import register_class


def build_class(model):
    base = model.get_relation_class('"half_orm_meta.api".field_access_in')

    class FieldAccessIn(base):
        @classmethod
        async def list_for(cls, access_id) -> list:
            from half_orm_gen.backend.ho_api.loader import resolve_field_names
            rows = await cls(access_id=access_id).ho_aselect('field_id')
            names = await resolve_field_names(cls._ho_model, [r['field_id'] for r in rows])
            return [names[r['field_id']] for r in rows if r['field_id'] in names]

        @classmethod
        async def add(cls, access_id, field_name: str) -> None:
            from half_orm_gen.backend.ho_api.loader import resolve_field_id
            field_id = await resolve_field_id(cls._ho_model, access_id, field_name)
            await cls(access_id=access_id, field_id=field_id).ho_ainsert()

        @classmethod
        async def add_batch(cls, access_id, field_names: list) -> None:
            for field_name in field_names:
                await cls.add(access_id, field_name)

        @classmethod
        async def remove(cls, access_id, field_name: str) -> bool:
            from half_orm_gen.backend.ho_api.loader import resolve_field_id
            try:
                field_id = await resolve_field_id(cls._ho_model, access_id, field_name)
            except ValueError:
                return False
            result = await cls(access_id=access_id, field_id=field_id).ho_adelete('*')
            return bool(result)

    return register_class(FieldAccessIn)
