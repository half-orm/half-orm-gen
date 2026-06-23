import os
import sys

cur_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, cur_dir)
par_dir = os.path.join(cur_dir, os.path.pardir)
sys.path.insert(0, par_dir)

from half_orm_gen.runtime import build_crud_app
from {module_name} import MODEL

try:
    from api.custom.middlewares import middlewares
except ImportError:
    middlewares = []

try:
    from api.custom.middlewares.authorization import Authorization
    _auth_middleware = [Authorization]
except ImportError:
    _auth_middleware = []

application = build_crud_app(
    MODEL,
    module_name='{module_name}',
    api_version={api_version},
    middleware=_auth_middleware + middlewares,
)