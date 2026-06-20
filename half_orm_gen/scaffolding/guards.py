"""
API guards for this project.

A guard is an async callable with the signature::

    async def my_guard(connection: ASGIConnection, handler: BaseRouteHandler) -> None:
        ...

It should raise ``NotAuthorizedException`` or ``HTTPException`` to deny access,
or return ``None`` to allow it.

Reference the guards by name in your ``@tools.api_*`` decorators::

    @tools.api_get('/items/{id: uuid}', guards=['connected'])
    async def get_item(self, request):
        ...

See https://docs.litestar.dev/latest/usage/security/guards.html
"""

from litestar.connection import ASGIConnection
from litestar.handlers.base import BaseRouteHandler
from litestar.exceptions import NotAuthorizedException, HTTPException


async def public(connection: ASGIConnection, handler: BaseRouteHandler = None) -> None:
    """Allow all requests."""
    return


async def connected(connection: ASGIConnection, handler: BaseRouteHandler = None) -> None:
    """Allow only authenticated users."""
    if connection.user:
        return
    raise NotAuthorizedException()


# ---------------------------------------------------------------------------
# Add your project-specific guards below.
# ---------------------------------------------------------------------------