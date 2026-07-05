"""
Peer management endpoints for federated identity ("half_orm_meta.identity").

All endpoints here require an active role of 'admin'. A separate public,
unauthenticated GET /auth/peers (in runtime.py, alongside the other
special handlers like /ho_setup) exposes just the name/url of trusted
peers, for the login page's "sign in via ..." buttons.

See planning/identite_federee.md for the design rationale — bilateral
trust: a peer only appears here because an admin explicitly registered it,
never automatically.
"""
import uuid
from typing import Any

from litestar import Request, get, post, put, delete
from litestar.exceptions import HTTPException

from half_orm_gen.backend.crud_helpers import _get_roles
from half_orm_gen.backend.ho_api.identity_models import HoIdentityModels


def _check_admin(request: Request) -> list[str]:
    roles = _get_roles(request)
    if 'admin' not in roles:
        raise HTTPException(
            status_code=403,
            detail=f'Admin access required (current roles: {roles})',
        )
    return roles


def make_identity_admin_handlers(model, prefix: str) -> list:
    identity = HoIdentityModels(model)

    @get(f'{prefix}/ho_admin/peer/self')
    async def identity_admin_self_peer(request: Request) -> dict:
        """This project's own federation identity — url + signing algorithm,
        and its public key when RS256 (the value other peers need to paste
        into their own `peer.jwt_public_key` when registering this project).
        """
        _check_admin(request)
        import os
        algorithm = os.environ.get('HO_JWT_ALGORITHM', 'HS256')
        public_key = None
        key_file = os.environ.get('HO_JWT_PUBLIC_KEY_FILE')
        if algorithm == 'RS256' and key_file:
            try:
                with open(key_file) as f:
                    public_key = f.read()
            except OSError:
                public_key = None
        return {
            'url': os.environ.get('HO_PEER_URL', ''),
            'algorithm': algorithm,
            'public_key': public_key,
        }

    @get(f'{prefix}/ho_admin/peer')
    async def identity_admin_list_peers(request: Request) -> list:
        _check_admin(request)
        return await identity.peer()().ho_aselect()

    @post(f'{prefix}/ho_admin/peer')
    async def identity_admin_create_peer(request: Request, data: dict[str, Any]) -> dict:
        _check_admin(request)
        name = data.get('name')
        url = data.get('url')
        jwt_public_key = data.get('jwt_public_key')
        if not name or not url:
            raise HTTPException(status_code=400, detail='name and url required')
        result = await identity.peer()(
            name=name, url=url, jwt_public_key=jwt_public_key,
        ).ho_ainsert()
        return result

    @put(f'{prefix}/ho_admin/peer/{{peer_id:str}}')
    async def identity_admin_update_peer(request: Request, peer_id: str, data: dict[str, Any]) -> dict:
        _check_admin(request)
        uid = uuid.UUID(peer_id)
        payload = {
            k: v for k, v in data.items()
            if k in ('name', 'url', 'jwt_public_key', 'trusted') and v is not None
        }
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
