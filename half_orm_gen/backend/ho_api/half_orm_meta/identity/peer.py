"""half_orm_meta.identity.peer — trusted federation peers.

See planning/identite_federee.md (section 4bis) for the design rationale
behind the registration-card exchange: a peer is registered by pasting a
single base64(JSON) blob the OTHER peer exports about itself (id, name,
url, frontend_url, jwt_public_key), never by typing those fields by hand.
Trust is bilateral but never automatically symmetric.
"""

import base64
import datetime
import json
import uuid
from typing import Any

from half_orm.model import register_class

#: Long enough to send a card out of band (email, chat, ...); regenerating
#: one costs nothing (just reopen the admin page).
REGISTRATION_KEY_TTL_SECONDS = 1800


def build_class(model):
    base = model.get_relation_class('"half_orm_meta.identity".peer')

    class Peer(base):
        @staticmethod
        def decode_registration_key(registration_key: str) -> dict[str, Any]:
            """Decode a peer's registration card (base64(JSON)) into its fields.

            No signature to verify here — trust comes from the channel the
            admin used to obtain this string from the other peer's admin,
            not from the encoding itself. The `expires_at` check is what
            actually matters security-wise. Raises ValueError on any
            invalid/malformed/expired key — the HTTP layer translates that
            to a 400.
            """
            try:
                payload = json.loads(base64.b64decode(registration_key).decode('utf-8'))
            except Exception:
                raise ValueError('Invalid registration key')
            missing = [
                k for k in ('id', 'name', 'url', 'jwt_public_key', 'expires_at')
                if not payload.get(k)
            ]
            if missing:
                raise ValueError(f'Registration key missing: {", ".join(missing)}')
            try:
                expires_at = datetime.datetime.fromisoformat(payload['expires_at'])
            except (ValueError, TypeError):
                raise ValueError('Registration key has an invalid expiry')
            if datetime.datetime.now(datetime.timezone.utc) > expires_at:
                raise ValueError('Registration key has expired — ask for a fresh one')
            try:
                payload['id'] = uuid.UUID(payload['id'])
            except (ValueError, TypeError):
                raise ValueError('Registration key has an invalid id (must be a uuid)')
            return payload

        @classmethod
        async def list_all(cls) -> list:
            return await cls().ho_aselect()

        @classmethod
        async def lookup_trusted(cls, peer_id) -> dict | None:
            rows = await cls(id=peer_id, trusted=True).ho_aselect('id', 'url')
            return rows[0] if rows else None

        @classmethod
        async def lookup(cls, peer_id) -> dict | None:
            rows = await cls(id=peer_id).ho_aselect('jwt_public_key', 'trusted')
            return rows[0] if rows else None

        @classmethod
        async def register_from_card(cls, registration_key: str) -> dict:
            card = cls.decode_registration_key(registration_key)
            return await cls(
                id=card['id'], name=card['name'], url=card['url'],
                frontend_url=card.get('frontend_url'), jwt_public_key=card['jwt_public_key'],
            ).ho_ainsert()

        @classmethod
        async def update_from(
            cls, peer_id, trusted: bool | None = None, registration_key: str | None = None,
        ) -> dict | None:
            """Returns the updated row, or None if peer_id doesn't exist.

            Raises ValueError if there's nothing to update, or if a
            supplied registration_key's id doesn't match peer_id.
            """
            payload: dict[str, Any] = {}
            if trusted is not None:
                payload['trusted'] = trusted
            if registration_key:
                card = cls.decode_registration_key(registration_key)
                if card['id'] != peer_id:
                    raise ValueError("Registration key's id does not match this peer")
                payload.update(
                    name=card['name'], url=card['url'],
                    frontend_url=card.get('frontend_url'), jwt_public_key=card['jwt_public_key'],
                )
            if not payload:
                raise ValueError('nothing to update')
            result = await cls(id=peer_id).ho_aupdate(**payload)
            return result[0] if result else None

        @classmethod
        async def delete(cls, peer_id) -> bool:
            result = await cls(id=peer_id).ho_adelete('*')
            return bool(result)

    return register_class(Peer)
