"""
Role composition decorators for half-orm-litestar.

Two decorators are provided:

- @authorize_and(role_name): both the decorated function AND the named role
  must return True (use for role refinement: "permanent IS a membre").

- @authorize_or(role_name): either the decorated function OR the named role
  must return True (use for alternative access paths).

Example::

    # api/roles/permanent.py
    from api.roles.core import authorize_and

    @authorize_and("membre")
    async def authorize(path_params, jwt_payload):
        return jwt_payload.is_permanent
"""

import importlib
from functools import wraps
from typing import Awaitable, Callable

AuthorizeFunc = Callable[[dict, object], Awaitable[bool]]


def authorize_and(role_name: str) -> Callable[[AuthorizeFunc], AuthorizeFunc]:
    """Compose authorization with AND logic.

    The named role's authorize() must return True AND the decorated function
    must return True.
    """
    def decorator(func: AuthorizeFunc) -> AuthorizeFunc:
        @wraps(func)
        async def wrapper(path_params: dict, jwt_payload) -> bool:
            role_module = importlib.import_module(f"api.roles.{role_name}")
            return (
                await role_module.authorize(path_params, jwt_payload)
                and await func(path_params, jwt_payload)
            )
        return wrapper
    return decorator


def authorize_or(role_name: str) -> Callable[[AuthorizeFunc], AuthorizeFunc]:
    """Compose authorization with OR logic.

    The named role's authorize() returning True OR the decorated function
    returning True is sufficient.
    """
    def decorator(func: AuthorizeFunc) -> AuthorizeFunc:
        @wraps(func)
        async def wrapper(path_params: dict, jwt_payload) -> bool:
            role_module = importlib.import_module(f"api.roles.{role_name}")
            return (
                await role_module.authorize(path_params, jwt_payload)
                or await func(path_params, jwt_payload)
            )
        return wrapper
    return decorator
