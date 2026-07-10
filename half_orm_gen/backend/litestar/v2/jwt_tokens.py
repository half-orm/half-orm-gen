"""
Shared JWT signing for locally-issued tokens (login/signup).

Reads HO_JWT_ALGORITHM (+ HO_JWT_SECRET or HO_JWT_PRIVATE_KEY_FILE) the same
way ho_api/authorization.py's middleware reads the matching verification
key — see scaffold.py's app.py bootstrap, which normalizes the key-file env
vars to absolute paths before anything else runs.
"""
import os

import jwt


def sign_token(
    user_id: str, roles: list[str], name: str | None = None, email: str | None = None,
) -> str:
    algorithm = os.environ.get('HO_JWT_ALGORITHM', 'HS256')
    if algorithm == 'RS256':
        key_file = os.environ['HO_JWT_PRIVATE_KEY_FILE']
        with open(key_file) as f:
            key = f.read()
    else:
        key = os.environ['HO_JWT_SECRET']
    payload: dict = {'sub': user_id, 'roles': roles}
    # name/email are only used by a peer we later delegate to (federation's
    # callback reads them to fill in a brand new "half_orm_meta.identity".
    # "user" row it creates for someone it's never seen before) — harmless
    # extra claims here.
    if name:
        payload['name'] = name
    if email:
        payload['email'] = email
    return jwt.encode(payload, key, algorithm=algorithm)
