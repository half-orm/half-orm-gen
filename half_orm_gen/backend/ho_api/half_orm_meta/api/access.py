"""half_orm_meta.api.access — one role's grant of one verb on one resource."""

from half_orm.model import register_class


def build_class(model):
    base = model.get_relation_class('"half_orm_meta.api".access')

    class Access(base):
        @classmethod
        async def list_for(cls, schema_name: str, table_name: str, verb: str) -> list:
            return await cls(schema_name=schema_name, table_name=table_name, verb=verb).ho_aselect()

        @classmethod
        async def resource_for(cls, access_id) -> str | None:
            rows = await cls(id=access_id).ho_aselect('schema_name', 'table_name')
            if not rows:
                return None
            return f"{rows[0]['schema_name']}/{rows[0]['table_name']}"

        @classmethod
        async def create(cls, role_name: str, schema: str, table: str, verb: str, parent_map: dict) -> tuple:
            """Create an access row. For non-DELETE verbs, also auto-grants
            the resource's PK field(s) as 'out' — unless already inherited
            from an ancestor role's access on the same resource/verb (the
            check_field_not_inherited trigger forbids duplicates).

            Returns (access_id, pk_fields).
            """
            result = await cls(
                role_name=role_name, schema_name=schema, table_name=table, verb=verb,
            ).ho_ainsert()
            access_id = result['id']
            pk_fields: list[str] = []
            if verb != 'DELETE':
                rel_cls = cls._ho_model.get_relation_class(f'{schema}.{table}')
                pk_fields = list(rel_cls()._ho_pkey.keys())
                FieldAccessOut = cls._ho_model.get_relation_class('"half_orm_meta.api".field_access_out')
                inherited_out: set = set()
                current = parent_map.get(role_name)
                while current:
                    anc_acc = await cls(
                        role_name=current, schema_name=schema, table_name=table, verb=verb,
                    ).ho_aselect('id')
                    if anc_acc:
                        anc_out = await FieldAccessOut(access_id=anc_acc[0]['id']).ho_aselect('field_name')
                        inherited_out.update(r['field_name'] for r in anc_out)
                    current = parent_map.get(current)
                for pk in pk_fields:
                    if pk not in inherited_out:
                        await FieldAccessOut(access_id=access_id, field_name=pk).ho_ainsert()
            return access_id, pk_fields

        @classmethod
        async def delete(cls, access_id) -> str | None:
            """Delete an access row. Returns the "schema/table" resource it
            belonged to (for the caller to reload), or None if it didn't exist."""
            resource = await cls.resource_for(access_id)
            result = await cls(id=access_id).ho_adelete('*')
            return resource if result else None

    return register_class(Access)
