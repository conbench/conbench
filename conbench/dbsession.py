"""
This is largely based on the nice
https://github.com/dtheodor/flask-sqlalchemy-session

patched for modern Werkzeug, patch modeled after
https://github.com/pallets-eco/flask-sqlalchemy/commit/3565f0587519168c5ea4301f6e4bfba8c2ac4dee?diff=split
Also see https://github.com/dtheodor/flask-sqlalchemy-session/issues/14

Provides an SQLAlchemy scoped session that creates unique sessions per Flask
request.
"""
import os

from flask import current_app
from sqlalchemy.orm import scoped_session
from werkzeug.local import LocalProxy

# This is the SQLAlchemy session object which is meant to be used outside
# HTTP request context.
from conbench.db import _session as out_of_req_context_db_session

__all__ = ["current_session", "flask_scoped_session"]

# Plan for only using threading.
from threading import get_ident as get_cur_thread


def _get_session():
    try:
        current_app._get_current_object()
    except RuntimeError as exc:
        if "Working outside of application context" in str(exc):
            # Note(JP):  In the special case of pytest-initiated DB interaction
            # via code that should only be called from HTTP request handlers
            # (but isn't) then there is no request context or not even a Flask
            # application context. For example from test code we call right into
            # functions in entities/_entity.py; and these are totally meant to
            # operate in request context usually.
            if os.environ.get("PYTEST_CURRENT_TEST"):
                return out_of_req_context_db_session
        # re-raise all other exceptions
        raise

    app = current_app._get_current_object()
    if not hasattr(app, "scoped_session"):
        raise AttributeError(
            "{0} has no 'scoped_session' attribute. You need to initialize it "
            "with a flask_scoped_session.".format(app)
        )
    return app.scoped_session


current_session = LocalProxy(_get_session)
"""Provides the current SQL Alchemy session within a request.

Will raise an exception if no :data:`~flask.current_app` is available or it has
not been initialized with a :class:`flask_scoped_session`
"""


class flask_scoped_session(scoped_session):
    """A :class:`~sqlalchemy.orm.scoping.scoped_session` whose scope is set to
    the Flask application context.
    """

    def __init__(self, session_factory, app=None):
        """
        :param session_factory: A callable that returns a
            :class:`~sqlalchemy.orm.session.Session`
        :param app: a :class:`~flask.Flask` application
        """
        super(flask_scoped_session, self).__init__(
            session_factory, scopefunc=get_cur_thread
        )
        # the _app_ctx_stack.__ident_func__ is the greenlet.get_current, or
        # thread.get_ident if no greenlets are used.
        # each Flask request is launched in a seperate greenlet/thread, so our
        # session is unique per request
        # _app_ctx_stack looks like internal API but is the only way to get to
        # the active application context without adding logic to figure out
        # whether threads, greenlets, or something else is used to create new
        # application contexts. Keep in mind to refactor if Flask changes its
        # public/private API towards this.
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        app.scoped_session = self

        @app.teardown_appcontext
        def remove_scoped_session(*args, **kwargs):
            # Note(JP): despite the name of the decorator above, this runs
            # after every request. From the Flask docs: "After the request is
            # dispatched and a response is generated and sent, the request
            # context is popped, which then pops the application context.
            # Immediately before they are popped, the teardown_request() and
            # teardown_appcontext() functions are executed". The remove method
            # is documented here:
            # https://docs.sqlalchemy.org/en/14/orm/contextual.html#sqlalchemy.orm.scoped_session.remove
            app.scoped_session.remove()
