"""
Decorators for exposing halfORM class methods as Litestar API routes.

Usage in a halfORM relation class::

    from half_orm_gen import tools

    class MyRelation(MODEL.get_relation_class('schema.table')):
        @tools.api_get('/items/{id: uuid}', guards=['connected'])
        async def get_item(self, request: "Request"):
            ...

        @tools.api_post('/items', guards=['connected'])
        async def create_item(self, request: "Request"):
            ...

The decorated methods are discovered by ``half_orm litestar generate`` which
produces the ``api/main.py`` Litestar application file.
"""

import inspect
from functools import wraps
from typing import Callable
from litestar import get, post, put, delete, patch


def create_api_decorator(http_method: str, litestar_decorator: Callable):
    """Create an api_* decorator that mirrors the signature of the given Litestar decorator."""
    litestar_sig = inspect.signature(litestar_decorator)

    def api_decorator(*args, **kwargs):
        bound_args = litestar_sig.bind(*args, **kwargs)
        bound_args.apply_defaults()

        def wrapper(func: Callable) -> Callable:
            @wraps(func)
            def inner(*func_args, **func_kwargs):
                return func(*func_args, **func_kwargs)

            inner.is_api_route = True
            inner.http_method = http_method
            inner.litestar_params = dict(bound_args.arguments)
            inner.metadata = {
                'signature': inspect.signature(func),
                'documentation': func.__doc__ or '',
                'litestar_decorator': litestar_decorator,
                'bound_arguments': bound_args,
            }
            return inner

        return wrapper

    api_decorator.__signature__ = litestar_sig
    api_decorator.__name__ = f"api_{http_method.lower()}"
    api_decorator.__doc__ = (
        f"API decorator for {http_method} routes. "
        f"Accepts the same arguments as litestar.{http_method.lower()}."
    )
    return api_decorator


api_get    = create_api_decorator('GET',    get)
api_post   = create_api_decorator('POST',   post)
api_put    = create_api_decorator('PUT',    put)
api_delete = create_api_decorator('DELETE', delete)
api_patch  = create_api_decorator('PATCH',  patch)


def ho_api_role(name: str):
    """Mark a method as a dynamic role resolver for CRUD access control.

    The method receives (self, request) and returns a list of accessible PKs.
    """
    def decorator(fn):
        fn._ho_api_role = name
        return fn
    return decorator


def ho_api_filter(name: str):
    """Mark a method as a named row filter for CRUD queries.

    The method receives (self, request) — self is the Relation instance
    carrying the query's other constraints, request gives access to the
    caller's identity (e.g. request.state.user). It must return the
    (possibly narrowed) predicate, typically ``self & <extra predicate>``.
    """
    def decorator(fn):
        fn._ho_api_filter = name
        return fn
    return decorator
