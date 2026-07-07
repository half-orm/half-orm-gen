from ._templates import _tpl


def _admin_roles_component_ts(version_prefix: str) -> str:
    return _tpl('ho_admin/admin-roles.component.ts').substitute(version_prefix=version_prefix)


def _admin_peers_component_ts(version_prefix: str) -> str:
    return _tpl('ho_admin/admin-peers.component.ts').substitute(version_prefix=version_prefix)
