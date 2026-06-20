"""
Authorization middleware.

Implement the ``Authorization`` class below to handle authentication for your
API (JWT, session cookies, API keys, etc.).

When present, it is automatically placed first in the middleware stack by
``api/main.py``.

Example (JWT bearer token)::

    import jwt
    from litestar.middleware import AbstractAuthenticationMiddleware, AuthenticationResult
    from litestar.connection import ASGIConnection

    SECRET = "change-me"

    class Authorization(AbstractAuthenticationMiddleware):
        async def authenticate_request(self, connection: ASGIConnection) -> AuthenticationResult:
            token = connection.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            try:
                payload = jwt.decode(token, SECRET, algorithms=["HS256"])
                return AuthenticationResult(user=payload["sub"], auth=token)
            except Exception:
                return AuthenticationResult(user=None, auth=None)

See https://docs.litestar.dev/latest/usage/security/abstract-authentication-middleware.html
"""

# TODO: implement Authorization
# from litestar.middleware import AbstractAuthenticationMiddleware, AuthenticationResult
# from litestar.connection import ASGIConnection
#
# class Authorization(AbstractAuthenticationMiddleware):
#     async def authenticate_request(self, connection: ASGIConnection) -> AuthenticationResult:
#         raise NotImplementedError