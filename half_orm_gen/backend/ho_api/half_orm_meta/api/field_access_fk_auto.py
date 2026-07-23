"""half_orm_meta.api.field_access_fk_auto — per-field FK auto-resolve rule."""

from half_orm.model import register_class

VALID_RULES = ('connected_user', 'context', 'select')


def build_class(model):
    base = model.get_relation_class('"half_orm_meta.api".field_access_fk_auto')

    class FieldAccessFkAuto(base):
        @classmethod
        async def list_for(cls, access_id) -> list:
            from half_orm_gen.backend.ho_api.loader import resolve_field_names
            rows = await cls(access_id=access_id).ho_aselect('field_id', 'resolve_rule')
            names = await resolve_field_names(cls._ho_model, [r['field_id'] for r in rows])
            return [
                {'field_name': names[r['field_id']], 'resolve_rule': r['resolve_rule']}
                for r in rows if r['field_id'] in names
            ]

        @classmethod
        async def set(cls, access_id, field_name: str, resolve_rule: str) -> None:
            from half_orm_gen.backend.ho_api.loader import resolve_field_id
            if resolve_rule not in VALID_RULES:
                raise ValueError(f'resolve_rule must be one of {VALID_RULES}')
            field_id = await resolve_field_id(cls._ho_model, access_id, field_name)
            existing = await cls(access_id=access_id, field_id=field_id).ho_aselect('id')
            if existing:
                await cls(access_id=access_id, field_id=field_id).ho_aupdate(resolve_rule=resolve_rule)
            else:
                await cls(
                    access_id=access_id, field_id=field_id, resolve_rule=resolve_rule
                ).ho_ainsert()

        @classmethod
        async def remove(cls, access_id, field_name: str) -> bool:
            from half_orm_gen.backend.ho_api.loader import resolve_field_id
            try:
                field_id = await resolve_field_id(cls._ho_model, access_id, field_name)
            except ValueError:
                return False
            result = await cls(access_id=access_id, field_id=field_id).ho_adelete('*')
            return bool(result)

    return register_class(FieldAccessFkAuto)
