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

from werkzeug.local import LocalProxy
from flask import _app_ctx_stack, current_app
from sqlalchemy.orm import scoped_session

# This is the SQLAlchemy session object which is meant to be used outside
# HTTP request context.
from conbench.db import _session


__all__ = ["current_session", "flask_scoped_session"]

# Plan for only using threading.
from threading import get_ident as get_cur_thread


def _get_session():
    # pylint: disable=missing-docstring, protected-access
    context = _app_ctx_stack.top
    if context is None:
        # Note(JP): in our pytest test suite we do database interaction with
        # tooling in entities/_entity.py which is meant to operate in a request
        # context; when used in the test suite there is however no
        # request/application context.
        if os.environ.get("PYTEST_CURRENT_TEST"):
            return _session

        raise RuntimeError(
            "Cannot access current_session when outside of an application " "context."
        )
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
        """Setup scoped session creation and teardown for the passed ``app``.

        :param app: a :class:`~flask.Flask` application
        """
        app.scoped_session = self

        @app.teardown_appcontext
        def remove_scoped_session(*args, **kwargs):
            # pylint: disable=missing-docstring,unused-argument,unused-variable
            app.scoped_session.remove()
