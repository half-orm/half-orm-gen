"""half_orm_meta.api.user_role — which roles a user has been granted."""

from half_orm.model import register_class


def build_class(model):
    base = model.get_relation_class('"half_orm_meta.api".user_role')

    class UserRole(base):
        @classmethod
        async def has_admin(cls) -> bool:
            """True if at least one user has been granted the 'admin' role —
            used to detect first-run state (no admin yet)."""
            rows = await cls(role_name='admin').ho_aselect('user_id')
            return bool(rows)

        @classmethod
        async def roles_for(cls, user_id) -> list:
            """This peer's OWN grants for this person — identity federates,
            role assignment doesn't (planning/identite_federee.md). A
            person delegated in from another peer for the first time has
            none yet (falls back to ['connected']); an admin can grant more
            afterwards, same as any local user."""
            rows = await cls(user_id=user_id).ho_aselect('role_name')
            return [r['role_name'] for r in rows] or ['connected']

        @classmethod
        async def grant(cls, user_id, role_name: str) -> None:
            await cls(user_id=user_id, role_name=role_name).ho_ainsert()

        @classmethod
        async def admin_ids(cls) -> set:
            rows = await cls(role_name='admin').ho_aselect('user_id')
            return {str(r['user_id']) for r in rows}

    return register_class(UserRole)
