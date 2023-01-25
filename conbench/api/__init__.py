import flask as f

from typing import Callable

api = f.Blueprint("api", __name__)

# Adding the `Callable` type annotation here removes a whole lot of 'Cannot
# determine type of "rule"'. These are as of a cyclic definition (/import). See
# `[has-type]` err code in
# https://mypy.readthedocs.io/en/stable/error_code_list.html Related:
# https://github.com/python/mypy/issues/6356
rule: Callable = api.add_url_rule


from ._errors import *  # noqa
from .auth import *  # noqa
from .benchmarks import *  # noqa
from .commits import *  # noqa
from .compare import *  # noqa
from .contexts import *  # noqa
from .hardware import *  # noqa
from .history import *  # noqa
from .index import *  # noqa
from .info import *  # noqa
from .runs import *  # noqa
from .users import *  # noqa
