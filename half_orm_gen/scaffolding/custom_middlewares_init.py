"""
Custom Litestar middlewares for this project.

Add your middleware classes here and list them in ``middlewares``.
They will be prepended to the middleware stack (after the optional
``Authorization`` middleware).

Example::

    from litestar.middleware import AbstractMiddleware

    class MyMiddleware(AbstractMiddleware):
        ...

    middlewares = [MyMiddleware]
"""

middlewares = []