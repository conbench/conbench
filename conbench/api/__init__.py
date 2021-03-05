import flask as f


api = f.Blueprint("api", __name__)
rule = api.add_url_rule


from ._errors import *
from .auth import *
from .benchmarks import *
from .compare import *
from .contexts import *
from .index import *
from .machines import *
from .runs import *
from .users import *
