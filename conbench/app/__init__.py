import flask as f

app = f.Blueprint("app", __name__)
rule = app.add_url_rule


from .auth import *  # noqa
from .batches import *  # noqa
from .benchmarks import *  # noqa
from .compare import *  # noqa
from .index import *  # noqa
from .runs import *  # noqa
from .users import *  # noqa
