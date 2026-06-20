"""
half-orm-gen — API and frontend generation for halfORM projects.

Decorate halfORM relation methods with ``@tools.api_*`` and run
``half_orm gen`` to produce a ready-to-run application.

Quick start::

    from half_orm_gen import tools

    class MyTable(MODEL.get_relation_class('schema.my_table')):

        @tools.api_get('/items/{id: uuid}', guards=['connected'])
        async def get_item(self, request: "Request"):
            ...
"""