import os
import sys

cur_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, cur_dir)
par_dir = os.path.join(cur_dir, os.path.pardir)
sys.path.insert(0, par_dir)

from half_orm_gen.runtime_fastapi import build_crud_app
from {module_name} import MODEL

application = build_crud_app(MODEL, module_name='{module_name}', api_version={api_version})
