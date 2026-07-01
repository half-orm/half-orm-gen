"""half_orm accessor classes for the "half_orm_meta.api" schema."""


class HoApiModels:
    """Provides half_orm Relation classes for "half_orm_meta.api" tables."""

    _SCHEMA = 'half_orm_meta.api'

    def __init__(self, model):
        self._model = model

    def _rel(self, table: str):
        return self._model.get_relation_class(f'"{self._SCHEMA}".{table}')

    def role(self):
        return self._rel('role')

    def route(self):
        return self._rel('route')

    def field(self):
        return self._rel('field')

    def access(self):
        return self._rel('access')

    def field_access_in(self):
        return self._rel('field_access_in')

    def field_access_out(self):
        return self._rel('field_access_out')

    def field_access_fk_auto(self):
        return self._rel('field_access_fk_auto')

    def field_access_searchable(self):
        return self._rel('field_access_searchable')

    def filter(self):
        return self._rel('filter')

    def access_filter(self):
        return self._rel('access_filter')

    def user_role(self):
        return self._rel('user_role')
