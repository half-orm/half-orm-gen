from ._templates import _tpl


def _home_component_ts(first_route: str) -> str:
    return _tpl('pages/home.component.ts').substitute()


def _schema_component_ts() -> str:
    return _tpl('pages/schema.component.ts').substitute()
