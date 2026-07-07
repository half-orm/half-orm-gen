from ._templates import _tpl


def _schema_component_spec_ts() -> str:
    return _tpl('pages/schema.component.spec.ts').substitute()
