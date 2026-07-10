"""half_orm_meta.api.field_access_fk_auto — per-field FK auto-resolve rule."""

from half_orm.model import register_class

VALID_RULES = ('connected_user', 'context', 'select')


def build_class(model):
    base = model.get_relation_class('"half_orm_meta.api".field_access_fk_auto')

    class FieldAccessFkAuto(base):
        @classmethod
        async def list_for(cls, access_id) -> list:
            return await cls(access_id=access_id).ho_aselect('field_name', 'resolve_rule')

        @classmethod
        async def set(cls, access_id, field_name: str, resolve_rule: str) -> None:
            if resolve_rule not in VALID_RULES:
                raise ValueError(f'resolve_rule must be one of {VALID_RULES}')
            existing = await cls(access_id=access_id, field_name=field_name).ho_aselect('id')
            if existing:
                await cls(access_id=access_id, field_name=field_name).ho_aupdate(resolve_rule=resolve_rule)
            else:
                await cls(
                    access_id=access_id, field_name=field_name, resolve_rule=resolve_rule
                ).ho_ainsert()

        @classmethod
        async def remove(cls, access_id, field_name: str) -> bool:
            result = await cls(access_id=access_id, field_name=field_name).ho_adelete('*')
            return bool(result)

    return register_class(FieldAccessFkAuto)
