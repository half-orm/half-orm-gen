"""half_orm_meta.identity.login_state — anti-CSRF state for the federation
login-delegation redirect/callback flow (planning/identite_federee.md
section 4) — single-use, short-lived, deleted once consumed.
"""

from half_orm.model import register_class


def build_class(model):
    base = model.get_relation_class('"half_orm_meta.identity".login_state')

    class LoginState(base):
        @classmethod
        async def create(cls, state: str, peer_id, return_to: str) -> None:
            await cls(state=state, peer_id=peer_id, return_to=return_to).ho_ainsert()

        @classmethod
        async def consume(cls, state: str) -> dict | None:
            """Fetch and delete (single-use) the login_state row for `state`.

            Returns {peer_id, return_to, created_at}, or None if not found
            (unknown or already-consumed state).
            """
            rows = await cls(state=state).ho_aselect('peer_id', 'return_to', 'created_at')
            if not rows:
                return None
            await cls(state=state).ho_adelete('*')
            return rows[0]

    return register_class(LoginState)
