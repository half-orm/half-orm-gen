"""
Peer management endpoints for federated identity ("half_orm_meta.identity").

All endpoints here require an active role of 'admin'. A separate public,
unauthenticated GET /auth/peers (in runtime.py, alongside the other
special handlers like /ho_setup) exposes just the id/name/url of trusted
peers, for the login page's "sign in via ..." buttons.

See planning/identite_federee.md (section 4bis) for the design rationale
behind the registration-card exchange: a peer is registered by pasting a
single base64(JSON) blob the OTHER peer exports about itself (id, name,
url, frontend_url, jwt_public_key), never by typing those fields by hand —
this is what keeps `name` consistent everywhere (self-declared, not
locally chosen) and `id` (HO_PEER_ID) usable as a stable cross-peer lookup
key, instead of a free-text name nobody else agrees on.

The two admins registering each other are not necessarily the same
person sitting at two browser tabs — the card is displayed so it can be
sent by whatever channel the two admins actually use (email, chat, ...),
not just copy-pasted within a single session. It therefore carries a
short expiry (`expires_at`) so a card that leaks into some semi-public
channel, or simply sits unused, stops being valid — regenerating one
costs nothing (just reopen the admin page).

Trust is bilateral but never automatically symmetric: a peer only appears
here because an admin explicitly pasted its card. Pasting it here says
nothing about whether that peer has done the same for you.
"""
import base64
import datetime
import json
import os
import uuid
from typing import Any

from litestar import Request, get, post, put, delete
from litestar.exceptions import HTTPException

from half_orm_gen.backend.crud_helpers import _get_roles
from half_orm_gen.backend.ho_api.identity_models import HoIdentityModels

_REGISTRATION_KEY_TTL_SECONDS = 1800  # 30 minutes — long enough to send it out of band


def _check_admin(request: Request) -> list[str]:
    roles = _get_roles(request)
    if 'admin' not in roles:
        raise HTTPException(
            status_code=403,
            detail=f'Admin access required (current roles: {roles})',
        )
    return roles


def _decode_registration_key(registration_key: str) -> dict[str, Any]:
    """Decode a peer's registration card (base64(JSON)) into its fields.

    No signature to verify here — trust comes from the channel the admin
    used to obtain this string from the other peer's admin, not from the
    encoding itself (see planning/identite_federee.md section 4bis). The
    `expires_at` check is what actually matters security-wise: it bounds
    how long a card is usable after being generated, regardless of which
    channel carried it.
    """
    try:
        payload = json.loads(base64.b64decode(registration_key).decode('utf-8'))
    except Exception:
        raise HTTPException(status_code=400, detail='Invalid registration key')
    missing = [k for k in ('id', 'name', 'url', 'jwt_public_key', 'expires_at') if not payload.get(k)]
    if missing:
        raise HTTPException(status_code=400, detail=f'Registration key missing: {", ".join(missing)}')
    try:
        expires_at = datetime.datetime.fromisoformat(payload['expires_at'])
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail='Registration key has an invalid expiry')
    if datetime.datetime.now(datetime.timezone.utc) > expires_at:
        raise HTTPException(status_code=400, detail='Registration key has expired — ask for a fresh one')
    try:
        payload['id'] = uuid.UUID(payload['id'])
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail='Registration key has an invalid id (must be a uuid)')
    return payload


def make_identity_admin_handlers(model, prefix: str) -> list:
    identity = HoIdentityModels(model)

    @get(f'{prefix}/ho_admin/peer/self')
    async def identity_admin_self_peer(request: Request) -> dict:
        """This project's own federation identity — the registration card
        (base64-encoded) to hand to trusted peers, plus its parts for display
        in the admin UI.
        """
        _check_admin(request)
        algorithm = os.environ.get('HO_JWT_ALGORITHM', 'HS256')
        public_key = None
        key_file = os.environ.get('HO_JWT_PUBLIC_KEY_FILE')
        if algorithm == 'RS256' and key_file:
            try:
                with open(key_file) as f:
                    public_key = f.read()
            except OSError:
                public_key = None

        peer_id = os.environ.get('HO_PEER_ID', '')
        name = os.environ.get('HO_PEER_NAME', '')
        url = os.environ.get('HO_PEER_URL', '')
        frontend_url = os.environ.get('HO_FRONTEND_URL', '')

        export_key = None
        expires_at = None
        if peer_id and name and url and public_key:
            expires_at = (
                datetime.datetime.now(datetime.timezone.utc)
                + datetime.timedelta(seconds=_REGISTRATION_KEY_TTL_SECONDS)
            ).isoformat()
            card = {
                'id': peer_id, 'name': name, 'url': url,
                'frontend_url': frontend_url, 'jwt_public_key': public_key,
                'expires_at': expires_at,
            }
            export_key = base64.b64encode(json.dumps(card).encode('utf-8')).decode('ascii')

        return {
            'id': peer_id,
            'name': name,
            'url': url,
            'frontend_url': frontend_url,
            'algorithm': algorithm,
            'public_key': public_key,
            'export_key': export_key,
            'export_key_expires_at': expires_at,
        }

    @get(f'{prefix}/ho_admin/peer')
    async def identity_admin_list_peers(request: Request) -> list:
        _check_admin(request)
        return await identity.peer()().ho_aselect()

    @post(f'{prefix}/ho_admin/peer')
    async def identity_admin_create_peer(request: Request, data: dict[str, Any]) -> dict:
        _check_admin(request)
        registration_key = data.get('registration_key')
        if not registration_key:
            raise HTTPException(status_code=400, detail='registration_key required')
        card = _decode_registration_key(registration_key)
        result = await identity.peer()(
            id=card['id'], name=card['name'], url=card['url'],
            frontend_url=card.get('frontend_url'),
            jwt_public_key=card['jwt_public_key'],
        ).ho_ainsert()
        return result

    @put(f'{prefix}/ho_admin/peer/{{peer_id:str}}')
    async def identity_admin_update_peer(request: Request, peer_id: str, data: dict[str, Any]) -> dict:
        _check_admin(request)
        uid = uuid.UUID(peer_id)
        payload: dict[str, Any] = {}
        if data.get('trusted') is not None:
            payload['trusted'] = data['trusted']
        if data.get('registration_key'):
            card = _decode_registration_key(data['registration_key'])
            if card['id'] != uid:
                raise HTTPException(status_code=400, detail="Registration key's id does not match this peer")
            payload.update(
                name=card['name'], url=card['url'],
                frontend_url=card.get('frontend_url'),
                jwt_public_key=card['jwt_public_key'],
            )
        if not payload:
            raise HTTPException(status_code=400, detail='nothing to update')
        result = await identity.peer()(id=uid).ho_aupdate(**payload)
        if not result:
            raise HTTPException(status_code=404)
        return result[0]

    @delete(f'{prefix}/ho_admin/peer/{{peer_id:str}}')
    async def identity_admin_delete_peer(request: Request, peer_id: str) -> None:
        _check_admin(request)
        uid = uuid.UUID(peer_id)
        result = await identity.peer()(id=uid).ho_adelete('*')
        if not result:
            raise HTTPException(status_code=404)

    return [
        identity_admin_self_peer,
        identity_admin_list_peers,
        identity_admin_create_peer,
        identity_admin_update_peer,
        identity_admin_delete_peer,
    ]
