from ._templates import _tpl

_TSCONFIG = _tpl('static/tsconfig.json').substitute()
_TSCONFIG_APP = _tpl('static/tsconfig.app.json').substitute()
_STYLES_CSS = _tpl('static/styles.css').substitute()
_GITIGNORE = _tpl('static/gitignore').substitute()
_LATEX_PIPE = _tpl('static/latex.pipe.ts').substitute()
_TAILWIND_CONFIG = _tpl('static/tailwind.config.js').substitute()
_POSTCSS_CONFIG = _tpl('static/postcss.config.js').substitute()
_MAIN_TS = _tpl('static/main.ts').substitute()
_APP_CONFIG_TS = _tpl('static/app.config.ts').substitute()
_STATE_REGISTRY = _tpl('static/state-registry.ts').substitute()


def _package_json(project_name: str) -> str:
    return _tpl('static/package.json').substitute(project_name=project_name)


def _angular_json(project_name: str) -> str:
    return _tpl('static/angular.json').substitute(project_name=project_name)


def _index_html(project_title: str) -> str:
    return _tpl('static/index.html').substitute(project_title=project_title)


def _proxy_conf(version_prefix: str) -> str:
    prefix = version_prefix or '/api'
    return (
        '{\n'
        f'  "{prefix}": {{\n'
        '    "target": "http://localhost:8000",\n'
        '    "secure": false,\n'
        '    "ws": true\n'
        '  }\n'
        '}\n'
    )
