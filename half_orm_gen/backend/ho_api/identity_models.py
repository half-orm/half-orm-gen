"""half_orm accessor classes for the "half_orm_meta.identity" schema."""


class HoIdentityModels:
    """Provides half_orm Relation classes for "half_orm_meta.identity" tables."""

    _SCHEMA = 'half_orm_meta.identity'

    def __init__(self, model):
        self._model = model

    def _rel(self, table: str):
        return self._model.get_relation_class(f'"{self._SCHEMA}".{table}')

    def peer(self):
        return self._rel('peer')

    def user(self):
        return self._rel('"user"')

    def login_state(self):
        return self._rel('login_state')
