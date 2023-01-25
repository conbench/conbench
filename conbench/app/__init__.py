import flask as f

from typing import Callable

app = f.Blueprint("app", __name__)
rule: Callable = app.add_url_rule


from .auth import *  # noqa
from .batches import *  # noqa
from .benchmarks import *  # noqa
from .compare import *  # noqa
from .hardware import *  # noqa
from .index import *  # noqa
from .robots import *  # noqa
from .runs import *  # noqa
from .users import *  # noqa
