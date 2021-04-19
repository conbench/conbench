import flask as f


app = f.Blueprint("app", __name__)
rule = app.add_url_rule


from .index import *  # noqa
from .auth import *  # noqa
from .batches import *  # noqa
from .benchmarks import *  # noqa
from .compare import *  # noqa
from .runs import *  # noqa
from .users import *  # noqa
