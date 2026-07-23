"""half_orm_meta.api.field_access_searchable — which fields feed FK-select/global search."""

from half_orm.model import register_class


def build_class(model):
    base = model.get_relation_class('"half_orm_meta.api".field_access_searchable')

    class FieldAccessSearchable(base):
        @classmethod
        async def list_for(cls, access_id) -> list:
            from half_orm_gen.backend.ho_api.loader import resolve_field_names
            rows = await cls(access_id=access_id).ho_aselect('field_id', 'role_name')
            names = await resolve_field_names(cls._ho_model, [r['field_id'] for r in rows])
            return [
                {'field_name': names[r['field_id']], 'role_name': r['role_name']}
                for r in rows if r['field_id'] in names
            ]

        @classmethod
        async def add(cls, access_id, field_name: str, role_name: str | None = None) -> None:
            from half_orm_gen.backend.ho_api.loader import resolve_field_id
            field_id = await resolve_field_id(cls._ho_model, access_id, field_name)
            kwargs = {'access_id': access_id, 'field_id': field_id}
            if role_name is not None:
                kwargs['role_name'] = role_name
            await cls(**kwargs).ho_ainsert()

        @classmethod
        async def remove(cls, access_id, field_name: str) -> bool:
            from half_orm_gen.backend.ho_api.loader import resolve_field_id
            try:
                field_id = await resolve_field_id(cls._ho_model, access_id, field_name)
            except ValueError:
                return False
            result = await cls(access_id=access_id, field_id=field_id).ho_adelete('*')
            return bool(result)

    return register_class(FieldAccessSearchable)
