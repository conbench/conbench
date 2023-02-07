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

import conbench.logger

try:
    __version__ = importlib_metadata.version(__name__)
except Exception:
    # When is this expected to happen?
    __version__ = importlib_metadata.version("conbench")

del importlib_metadata


# Pre-configure logging before reading user-given configuration.
conbench.logger.setup(level_stderr="DEBUG", level_file=None, level_sqlalchemy="WARNING")
log = logging.getLogger(__name__)

# This is going to be an application-global singleton (in the webapp, not the
# CLI).
metrics = None


def create_application(config):
    global metrics

    import flask as f
    from prometheus_flask_exporter.multiprocess import GunicornInternalPrometheusMetrics

    app = f.Flask(__name__)
    app.config.from_object(config)

    _init_application(app)

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

    # Use `GunicornPrometheusMetrics` when spawning a separate HTTP server for
    # the metrics scrape endpoing. Note that this sets the global singleton.
    # This needs PROMETHEUS_MULTIPROC_DIR to be set to a path to a directory.
    _inspect_prom_multiproc_dir()
    metrics = GunicornInternalPrometheusMetrics(app)

    return app


def _inspect_prom_multiproc_dir():
    """
    Log information about the environment variable PROMETHEUS_MULTIPROC_DIR
    and about the path it points to. This is helpful for debugging bad state.
    """
    path = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    log.info("env PROMETHEUS_MULTIPROC_DIR: `%s`", path)

    if not path:
        return

    try:
        log.info("os.path.isdir('%s'): %s", path, os.path.isdir(path))
    except OSError as exc:
        log.info("os.path.isdir('%s') failed: %s", path, exc)


def _init_application(application):
    import flask_swagger_ui
    import werkzeug.exceptions

    from .api import api
    from .app import app
    from .config import Config
    from .db import configure_engine, create_all
    from .extensions import bootstrap, login_manager

    bootstrap.init_app(application)
    login_manager.init_app(application)
    api_docs = flask_swagger_ui.get_swaggerui_blueprint(
        "/api/docs",
        "/api/docs.json",
        config={"app_name": Config.APPLICATION_NAME},
    )
    configure_engine(application.config["SQLALCHEMY_DATABASE_URI"])

    # Do not create all tables when running alembic migrations in
    # production (CREATE_ALL_TABLES=false) using k8s migration job
    if Config.CREATE_ALL_TABLES:
        log.debug("Config.CREATE_ALL_TABLES appears to be set, call create_all()")
        create_all()

    application.register_blueprint(app, url_prefix="/")
    application.register_blueprint(api, url_prefix="/api")
    application.register_blueprint(api_docs, url_prefix="/api/docs")
    application.register_error_handler(
        werkzeug.exceptions.HTTPException, _json_http_errors
    )
    _init_api_docs(application)

    def _dated_url_for(endpoint, **values):
        import flask as f

        # add time to static assets to force cache invalidation
        if endpoint == "static":
            filename = values.get("filename", None)
            if filename:
                file_path = os.path.join(application.root_path, endpoint, filename)
                values["q"] = int(os.stat(file_path).st_mtime)
        return f.url_for(endpoint, **values)

    @application.context_processor
    def override_url_for():
        return dict(url_for=_dated_url_for)


def _init_api_docs(application):
    from .api._docs import spec

    with application.test_request_context():
        for fn_name in application.view_functions:
            if not fn_name.startswith("api."):
                continue
            view_fn = application.view_functions[fn_name]
            spec.path(view=view_fn)


def _json_http_errors(e):
    import flask as f

    response = e.get_response()
    data = {"code": e.code, "name": e.name}
    if e.code == 400:
        data["description"] = e.description
    response.data = f.json.dumps(data)
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


# Note(JP): when FLASK_APP is set then this here is not executed, but instead
# gunicorn loads into the app using a stringified import instruction such as
# `conbench:application` (codified in the gunicorn cmd line args).
# see .flaskenv used by `$ flask run`
if os.environ.get("FLASK_APP", None):
    from .config import Config
    from .db import Session

    application = create_application(Config)

    @application.teardown_appcontext
    def cleanup(_):
        Session.remove()
