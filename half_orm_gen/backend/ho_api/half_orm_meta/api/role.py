"""half_orm_meta.api.role — static and dynamic (@ho_api_role) roles."""

from half_orm.model import register_class

_SYSTEM_ROLES = [
    ('anonymous', False, None),
    ('connected', False, 'anonymous'),
    ('admin',     False, 'connected'),
]


def build_class(model):
    base = model.get_relation_class('"half_orm_meta.api".role')

    class Role(base):
        @classmethod
        async def ensure_system_roles(cls) -> None:
            """Insert each system role individually if not already present."""
            for name, deletable, parent_name in _SYSTEM_ROLES:
                if not await cls(name=name).ho_aselect('name'):
                    await cls(name=name, deletable=deletable, parent_name=parent_name).ho_ainsert()

        @classmethod
        async def load_parents(cls) -> dict:
            """Return {role_name: parent_name} for all roles."""
            rows = await cls().ho_aselect('name', 'parent_name')
            return {r['name']: r['parent_name'] for r in rows}

        @classmethod
        async def load_roles_info(cls) -> list:
            """Return [{name, schema_name, table_name}, ...] for all roles.

            Used by the public /ho_roles endpoint. schema_name/table_name
            are None for a normal (static) role, set for a dynamic one
            (registered via @ho_api_role — see registry.py) — that's what
            makes it dynamic, and what a client uses to know which
            resource's permissions matrix should offer it as a row.
            """
            rows = await cls().ho_aselect('name', 'schemaname', 'relname')
            return [
                {'name': r['name'], 'schema_name': r['schemaname'], 'table_name': r['relname']}
                for r in rows
            ]

        @classmethod
        async def list_all(cls, dynamic_role_names: set) -> list:
            """Return [{name, deletable, parent_name, kind}, ...] for the
            admin roles panel. `dynamic_role_names` is passed in rather than
            looked up here — the registry of @ho_api_role methods lives in
            Python (registry.py), not in this table.
            """
            rows = await cls().ho_aselect()
            return [
                {
                    'name':        r['name'],
                    'deletable':   r['deletable'],
                    'parent_name': r['parent_name'],
                    'kind': (
                        'dynamic' if r['name'] in dynamic_role_names
                        else 'system' if not r['deletable']
                        else 'user'
                    ),
                }
                for r in rows
            ]

        @classmethod
        async def register_dynamic(cls, schema: str, table: str, role_name: str) -> None:
            """Ensure the DB row for a role registered via @ho_api_role exists
            and is marked non-deletable/scoped to its resource.

            deletable=False: this role is hardcoded via @ho_api_role on the
            resource class — deleting the DB row would be pointless,
            discover_and_register re-creates it on every startup anyway.
            """
            existing = await cls(name=role_name).ho_aselect('deletable', 'schemaname', 'relname')
            if not existing:
                await cls(
                    name=role_name, deletable=False,
                    schemaname=schema, relname=table,
                ).ho_ainsert()
            elif (
                existing[0]['deletable']
                or existing[0]['schemaname'] != schema
                or existing[0]['relname'] != table
            ):
                # Self-heal a row created before this deletable=False /
                # schemaname+relname fix landed.
                await cls(name=role_name).ho_aupdate(
                    deletable=False, schemaname=schema, relname=table,
                )

        @classmethod
        async def create(cls, name: str, parent_name: str) -> None:
            await cls(name=name, deletable=True, parent_name=parent_name).ho_ainsert()

        @classmethod
        async def delete(cls, name: str) -> bool:
            """Delete a role. Returns False if it didn't exist.

            Raises the underlying ForeignKeyViolation if it still has child
            roles or granted accesses — the caller (HTTP layer) decides how
            to turn that into a 409.
            """
            result = await cls(name=name).ho_adelete('*')
            return bool(result)

        @classmethod
        async def set_parent(cls, name: str, parent_name: str | None) -> bool:
            result = await cls(name=name).ho_aupdate(parent_name=parent_name)
            return bool(result)

    return register_class(Role)
