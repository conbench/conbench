import flask as f

api = f.Blueprint("api", __name__)
rule = api.add_url_rule


from ._errors import *  # noqa
from .auth import *  # noqa
from .benchmarks import *  # noqa
from .commits import *  # noqa
from .compare import *  # noqa
from .contexts import *  # noqa
from .history import *  # noqa
from .index import *  # noqa
from .machines import *  # noqa
from .runs import *  # noqa
from .users import *  # noqa
