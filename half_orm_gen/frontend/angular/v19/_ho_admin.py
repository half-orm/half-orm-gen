from ._templates import _tpl


def _ho_admin_component_ts(version_prefix: str) -> str:
    return _tpl('ho_admin/ho-admin.component.ts').substitute(version_prefix=version_prefix)
