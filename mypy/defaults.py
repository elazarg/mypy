from typing import NamedTuple
from enum import Enum

class Version(NamedTuple('Version', [('major', int), ('minor', int)]), Enum):
    PYTHON2 = (2, 7)
    PYTHON3 = (3, 5)
MYPY_CACHE = '.mypy_cache'
