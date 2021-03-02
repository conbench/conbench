import flask as f


app = f.Blueprint("app", __name__)
rule = app.add_url_rule


from .index import *
from .auth import *
from .batches import *
from .benchmarks import *
from .compare import *
from .runs import *
from .series import *
from .users import *
