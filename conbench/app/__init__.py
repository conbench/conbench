from typing import Callable

import flask as f

app = f.Blueprint("app", __name__)
rule: Callable = app.add_url_rule


from .auth import *  # noqa
from .batches import *  # noqa
from .compare import *  # noqa
from .hardware import *  # noqa
from .index import *  # noqa
from .results import *  # noqa
from .robots import *  # noqa
from .runs import *  # noqa

# Note(JP): The asterisk globby import is difficult to work with. I think
# before this next line of code there is a module-global name User. Then `from
# .users import *` implicitly overwrites that module-global name with a
# different object. And that object has a different type of the other object.
# (mypy error:  error: Incompatible import of "User" (imported name has type
# "Type[conbench.app.users.User]", local name has type
# "Type[conbench.entities.user.User]"))
from .users import *  # type: ignore # noqa
