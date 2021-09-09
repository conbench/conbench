import os


def create_application(config):
    import flask as f

    application = f.Flask(__name__)
    application.config.from_object(config)
    _init_application(application)
    return application


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


# see .flaskenv used by `$ flask run`
if os.environ.get("FLASK_APP", None):
    from .config import Config
    from .db import Session

    application = create_application(Config)

    @application.teardown_appcontext
    def cleanup(_):
        Session.remove()
