"""
Generation of Litestar route handlers from @api_* decorated halfORM methods.
"""

import importlib
import inspect
import re
from typing import Iterable, Tuple, Type

from half_orm.relation import Relation

from half_orm_gen import templates as T

_RE_PATH_VAR = re.compile(r'\{([^:]*):([^\}]*)\}')

_LITESTAR_INTERNAL_PARAMS = {
    'operation_class', 'operation_id', 'tags', 'summary',
    'response_description', 'responses', 'deprecated',
    'cache', 'etag', 'return_dto', 'dto', 'type_encoders',
    'sync_to_thread', 'opt', 'signature_namespace',
    'include_in_schema', 'security', 'middleware',
}

_LITESTAR_DEFAULT_VALUES = {
    'cache': False,
    'deprecated': False,
    'sync_to_thread': True,
    'include_in_schema': True,
}


def _path_params(api_path: str) -> str:
    parts = [f'{var}: Any' for var, _ in re.findall(_RE_PATH_VAR, api_path)]
    return ', '.join(parts)


def _annotation_str(annotation) -> str:
    """Return a valid Python expression string for a type annotation."""
    if hasattr(annotation, '__name__'):
        mod = getattr(annotation, '__module__', None)
        if mod and mod != 'builtins':
            return f'{mod}.{annotation.__name__}'
        return annotation.__name__
    if hasattr(annotation, '__qualname__'):
        mod = getattr(annotation, '__module__', None)
        if mod and mod != 'builtins':
            return f'{mod}.{annotation.__qualname__}'
        return annotation.__qualname__
    return str(annotation)


def _query_params(signature: inspect.Signature):
    params_decl = []
    params_call = []
    for name, param in signature.parameters.items():
        if name == 'self':
            continue
        params_call.append(name)
        decl = name
        if param.annotation is not inspect.Parameter.empty:
            decl = f'{decl}: {_annotation_str(param.annotation)}'
        if param.default is not inspect.Parameter.empty:
            decl = f'{decl}={param.default!r}'
        params_decl.append(decl)
    return ', '.join(params_decl), ', '.join(params_call)


def _extract_guards(litestar_params: dict) -> list:
    guards = litestar_params.get('guards') or []
    result = []
    for g in guards:
        if hasattr(g, '__name__'):
            result.append(g.__name__)
        elif isinstance(g, str):
            result.append(g)
        else:
            result.append(str(g))
    return result


def _format_litestar_args(
    litestar_params: dict, guards_list: list, method_doc: str, api_version
) -> str:
    args = []

    if 'path' in litestar_params:
        version_prefix = f'/v{api_version}' if api_version is not None else ''
        full_path = f"{version_prefix}{litestar_params['path']}"
        args.append(f'"{full_path}"')

    kwargs = []

    if guards_list:
        guards_str = ', '.join(f'guards.{g}' for g in guards_list)
        kwargs.append(f'guards=[{guards_str}]')

    if litestar_params.get('name'):
        kwargs.append(f'name="{litestar_params["name"]}"')

    desc_parts = [p for p in [method_doc, f"Guards: {', '.join(guards_list)}" if guards_list else ''] if p]
    if desc_parts:
        kwargs.append(f'description="""{chr(10).join(desc_parts)}"""')
    elif litestar_params.get('description'):
        kwargs.append(f'description="""{litestar_params["description"]}"""')

    for key, value in litestar_params.items():
        if key in ('path', 'guards', 'name', 'description'):
            continue
        if key in _LITESTAR_INTERNAL_PARAMS:
            continue
        if key in _LITESTAR_DEFAULT_VALUES and value == _LITESTAR_DEFAULT_VALUES[key]:
            continue
        if hasattr(value, '__class__'):
            cls = value.__class__
            if 'Empty' in str(cls) or 'enum' in str(cls).lower():
                continue
            if cls.__module__ not in ('builtins', '__builtin__'):
                continue
        if isinstance(value, str):
            kwargs.append(f'{key}="{value}"')
        elif isinstance(value, bool):
            kwargs.append(f'{key}={value}')
        elif isinstance(value, (int, float)):
            kwargs.append(f'{key}={value}')
        elif value is not None:
            kwargs.append(f'{key}={value!r}')

    return ', '.join(args + kwargs)


def generate_api_routes(
    classes: Iterable[Tuple[Type[Relation], str]],
    api_version,
) -> Tuple[list, list]:
    """Scan @api_* decorated methods and return (blocks, route_handler_names).

    Also returns the set of (module_str, verb) pairs already covered, so the
    CRUD generator can skip them.
    """
    blocks: list[str] = []
    route_handlers: list[str] = []
    covered: set[tuple] = set()   # (module_str, verb) covered by @api_*

    for relation, _relation_type in classes:
        module_str   = relation.__module__
        schema       = '.'.join(module_str.split('.')[:-1])
        module_name  = module_str.split('.')[-1]
        module_alias = module_str.replace('.', '_')

        schema_cap   = ''.join(p.capitalize() for p in relation._schemaname.split('.'))

        api_methods = [
            (name, method)
            for name, method in inspect.getmembers(relation, predicate=inspect.isfunction)
            if getattr(method, 'is_api_route', False) and name in relation.__dict__
        ]

        if not api_methods:
            mod = importlib.import_module(module_str)
            if hasattr(mod, 'API'):
                for func in mod.API:
                    alias = str(func).replace('.', '_')
                    fname = str(func).split('.')[-1]
                    blocks.append(T.DIRECT_API.format(
                        module_str=module_str,
                        function=fname,
                        function_alias=alias,
                    ))
                    route_handlers.append(alias)
            continue

        blocks.append(T.IMPORT.format(
            schema=schema,
            module_name=module_name,
            module_alias=module_alias,
        ))

        for name, method in api_methods:
            litestar_params = method.litestar_params
            metadata        = method.metadata
            verb            = method.http_method
            guards_list     = _extract_guards(litestar_params)
            sig             = metadata.get('signature', inspect.signature(method))
            query_params, call_params = _query_params(sig)
            litestar_args = _format_litestar_args(
                litestar_params, guards_list, metadata.get('documentation', ''),
                api_version,
            )

            full_name = f'{module_alias}_{name}'
            template  = T.HTTP.get(verb)
            if template is None:
                print(f'  warning: no template for HTTP method {verb} ({module_str}.{name})')
                continue

            print(f'  {verb:6s} {litestar_params.get("path", "")} → {full_name}')

            blocks.append(template.format(
                full_name    = full_name,
                litestar_args= litestar_args,
                dc_name      = relation._ho_dataclass_name(),
                module_alias = module_alias,
                class_name   = relation.__name__,
                path_params  = _path_params(litestar_params.get('path', '')),
                query_params = query_params,
                params       = call_params,
                name         = name,
            ))
            route_handlers.append(full_name)
            covered.add((module_str, verb))

        mod = importlib.import_module(module_str)
        if hasattr(mod, 'API'):
            for func in mod.API:
                alias = str(func).replace('.', '_')
                fname = str(func).split('.')[-1]
                blocks.append(T.DIRECT_API.format(
                    module_str=module_str,
                    function=fname,
                    function_alias=alias,
                ))
                route_handlers.append(alias)

    return blocks, route_handlers, covered
