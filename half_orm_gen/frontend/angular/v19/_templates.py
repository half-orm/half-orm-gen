from functools import lru_cache
from pathlib import Path
from string import Template

_ROOT = Path(__file__).parent / 'templates'


@lru_cache(maxsize=None)
def _tpl(relpath: str) -> Template:
    return Template((_ROOT / relpath).read_text())
