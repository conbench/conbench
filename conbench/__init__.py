"""
Note: this module gets loaded both, when

- invoking the (legacy) Conbench CLI
- running the Conbench web application

There should be cleaner separation of concerns in the future, and cleanly
separate dependency considerations.

Certain modules which are needed only in the web application can be imported
in `create_application()` below.

Also see https://github.com/conbench/conbench/pull/662#discussion_r1097781344
"""

import importlib.metadata as importlib_metadata
import json
import logging
import os
import traceback
from typing import TYPE_CHECKING

import conbench.logger

try:
    __version__ = importlib_metadata.version(__name__)
except Exception:
    # When is this expected to happen? Is this meant for the CLI code path?
    # Or for the web app? TODO: https://github.com/conbench/conbench/issues/617
    __version__ = importlib_metadata.version("conbench")

del importlib_metadata


if TYPE_CHECKING:
    # https://stackoverflow.com/a/39757388/145400
    # Yes one could do `-> "flask.Response"`` but then
    # https://github.com/PyCQA/pyflakes/issues/340  ¯\_(ツ)_/¯
    import flask
    import werkzeug
    import werkzeug.exceptions


# Pre-configure logging before reading user-given configuration.
conbench.logger.setup(level_stderr="DEBUG", level_file=None, level_sqlalchemy="WARNING")
log = logging.getLogger(__name__)


def create_application(config) -> "flask.Flask":
    import flask as f
    import flask_compress

    import conbench.metrics

    app = f.Flask(__name__)
    app.config.from_object(config)

    _init_flask_application(app)

    # Re-configure logging using user-given configuration details.
    log.debug("re-configure logging")
    conbench.logger.setup(
        level_stderr=app.config["LOG_LEVEL_STDERR"],
        level_file=app.config["LOG_LEVEL_FILE"],
        level_sqlalchemy=app.config["LOG_LEVEL_SQLALCHEMY"],
    )

    # The global Config object is different from Flask's application.config
    # object. Here, log Flask's config object which contains more keys. Note:
    # sanitize sensitive configuration values so that the INFO log of the app
    # does not contain obvious secrets -- this needs constant review of the
    # `to_nonsensitive_string()`` method
    log_cfg_msg = (
        "Flask app config object:\n"
        + dict_or_objattrs_to_nonsensitive_string(app.config)
        + "\n\n"
        + "Conbench config object:\n"
        + dict_or_objattrs_to_nonsensitive_string(config)
    )

    # In non-testing, INFO-log the configuration details. In testing, DEBUG-log
    # them (in the test suite, the app gets re-initialized for each test).
    # Note: this is an attempt to control log verbosity of the test suite.
    # Maybe change the test suite to init the app object only once.
    if app.config["TESTING"]:
        log.debug(log_cfg_msg)
    else:
        log.info(log_cfg_msg)

    # This mutates `app` in-place.
    conbench.metrics.decorate_flask_app_with_metrics(app)

    # This also mutates the app in-place, sets up
    # https://github.com/colour-science/flask-compress for deployments that do
    # not run an HTTP reverse proxy with proper response compression in front
    # of Conbench. Conbench amy emit large JSON and HTML responses, and simple
    # gzip compression yields huge value.
    flask_compress.Compress().init_app(app)

    return app


def _init_flask_application(app):
    import flask
    import flask_swagger_ui
    import werkzeug.exceptions

    from conbench.dbsession import flask_scoped_session

    from .api import api
    from .app import app as blueprint_app
    from .config import Config
    from .db import configure_engine, create_all, session_maker

    # Note(JP): maybe this bootstrap extension doesn't do too much work for us.
    # We use `quick_form()` here and there, and that is tied to bootstrap 3.
    # Looks like we want to do that UI work 'manually' (it is not a lot of
    # work), and can then remove this extension.
    from .extensions import bootstrap, login_manager

    bootstrap.init_app(app)
    login_manager.init_app(app)

    api_docs = flask_swagger_ui.get_swaggerui_blueprint(
        "/api/docs",
        "/api/docs.json",
        config={"app_name": Config.APPLICATION_NAME},
    )
    configure_engine(app.config["SQLALCHEMY_DATABASE_URI"])

    # This is a tiny helper that manages a per-request SQLAlchemy session which
    # can be obtained via `current_session` (from flask_sqlalchemy_session
    # import current_session) within a request context. Via the
    # `@app.teardown_appcontext` interface, such a session is guaranteed to get
    # its `remove()` method called when leaving a request context. That's the
    # recommended pattern to make sure a fresh SQLAlchemy session is is used
    # for each HTTP request.
    # https://docs.sqlalchemy.org/en/20/orm/contextual.html#using-thread-local-scope-with-web-applications
    flask_scoped_session(session_maker, app)

    # Do not create all tables when running alembic migrations in
    # production (CREATE_ALL_TABLES=false) using k8s migration job
    if Config.CREATE_ALL_TABLES:
        log.debug("Config.CREATE_ALL_TABLES appears to be set, call create_all()")
        create_all()

    app.register_blueprint(blueprint_app, url_prefix="/")
    app.register_blueprint(api, url_prefix="/api")
    app.register_blueprint(api_docs, url_prefix="/api/docs")
    app.register_error_handler(werkzeug.exceptions.HTTPException, _json_http_errors)
    app.register_error_handler(Exception, _handle_all_other_exceptions)

    _init_api_docs(app)

    @app.before_request
    def deny_common_bots():
        """
        Terminate request processing by emitting a 403 response if the user
        agent string is part of a denylist.

        https://github.com/conbench/conbench/issues/1012
        https://flask.palletsprojects.com/en/2.2.x/api/#flask.Flask.before_request
        Note on case sensitivity: https://stackoverflow.com/a/57562733/145400
        """
        denylist = ["dataforseobot", "dotbot", "petalbot"]
        ua = flask.request.headers.get("User-Agent")
        if ua:  # not None, not empty string
            haystack = ua.lower()
            for needle in denylist:
                if needle in haystack:
                    return flask.make_response(("unexpected user agent", 403))


def _init_api_docs(application):
    from .api._docs import spec

    with application.test_request_context():
        for fn_name in application.view_functions:
            if not fn_name.startswith("api."):
                continue
            view_fn = application.view_functions[fn_name]
            spec.path(view=view_fn)


def _handle_all_other_exceptions(exc):
    """
    "If you register handlers for both HTTPException and Exception, the
    Exception handler will not handle HTTPException subclasses because it the
    HTTPException handler is more specific"
    """
    import flask as f

    # For now: even in 'prod', expose the traceback corresponding to the
    # exception in an HTTP 500 response, facilitating debugging; so that users
    # can send tracebacks right away.
    tbstr = "".join(traceback.format_exception(exc))
    resp = f.make_response((f"unexpected exception, please report this:\n{tbstr}", 500))
    resp.headers["Content-Type"] = "text/plain"
    return resp


def _json_http_errors(exc) -> "werkzeug.wrappers.Response":
    """
    Seems to be guaranteed to only be called for
    werkzeug.exceptions.HTTPException.

    Turn an HTTPException object into a JSON response where exception detail is
    emitted as part of the JSON document.
    See https://github.com/conbench/conbench/issues/1181.
    """
    # Note(JP): I understand this is against cyclic imports, but having this as
    # part of frequently called error handler (even if the import machinery is
    # fast and cached) is a code smell -- let's see about this.
    import flask as f

    # "Return JSON instead of HTML for HTTP errors"
    # From https://flask.palletsprojects.com/en/2.2.x/errorhandling/#generic-exception-handlers
    # start with the correct headers and status code from the error
    response = exc.get_response()
    response.data = f.json.dumps(
        {
            "code": exc.code,
            "name": exc.name,
            "description": exc.description,
        }
    )
    response.content_type = "application/json"
    return response


def dict_or_objattrs_to_nonsensitive_string(obj):
    """Generate a sorted and indented JSON string from the keys and values
    given by `obj`. Sanitize values if they appear to be sensitive.

    If `obj` looks like a dictionary then take keys and values from there.

    For all other object types use `dir(obj)` to look up instance and class
    attributes, but ignore all those that start with an underscore.
    """

    # Fragments are matched w/o considering case.
    sensitive_key_fragments = [
        "SECRET",
        "REGISTRATION_KEY",
        "PASSWORD",
        "TOKEN",
        "SQLALCHEMY_DATABASE_URI",
    ]

    if isinstance(obj, dict):
        keys = list(obj.keys())
        values = list(obj.values())
    else:
        keys = list(k for k in dir(obj) if not k.startswith("_"))
        values = [getattr(obj, k) for k in keys]

    sanitized = {}

    # Iterate over all object and class attributes,
    for k, v in zip(keys, values):
        if not isinstance(k, str):
            # We may get here when `obj` is a dictionary with non-string keys.
            # Ignore those keys in textual output.
            continue

        if not isinstance(v, str):
            # Keep Nones and booleans as they are (stringified after all
            # by json.dumps() below)
            sanitized[k] = v
            continue

        for fragment in sensitive_key_fragments:
            if fragment.lower() in k.lower():
                # If the 'secret' is shorter than four characters then this
                # will reveal the entire secret. That's OK, an actual
                # secret should be way longer.
                sanitized[k] = "*******" + v[-3:]
                break
        else:
            # `else` should have been called `nobreak`. That's what it is :)
            # Key appears to be non-senstive, take value as-is.
            sanitized[k] = v

    return json.dumps(sanitized, sort_keys=True, default=str, indent=2)


# Leaving the `os.environ.get("FLASK_APP", None)` in here although I really
# don't quite understand intent and purpose.
if os.environ.get("FLASK_APP", None):
    from .config import Config

    application = create_application(Config)

# Note(JP): when FLASK_APP is set then this here is not executed, but instead
# gunicorn loads into the app using a stringified import instruction such as
# `conbench:application` (codified in the gunicorn cmd line args). see
# .flaskenv used by `$ flask run` Note(JP): oh wow, this is probably how with
# the gunicorn deployment we never ran this Session.remove() between requests.
# if os.environ.get("FLASK_APP", None):
#     from .config import Config
#     from .db import Session
#     application = create_application(Config)
#     @application.teardown_appcontext
#     def cleanup(_):
#         Session.remove()
