import datetime

import flask as f
import flask_login
import marshmallow
from sqlalchemy.sql import text

from .. import __version__
from ..api import api, rule
from ..api._docs import spec
from ..api._endpoint import ApiEndpoint
from ..db import Session


@api.route("/docs.json")
def docs():
    return f.jsonify(spec.to_dict())


class IndexSerializer:
    def dump(self):
        return {
            "links": {
                "benchmarks": f.url_for("api.benchmarks", _external=True),
                "commits": f.url_for("api.commits", _external=True),
                "contexts": f.url_for("api.contexts", _external=True),
                "docs": f.url_for("api.docs", _external=True),
                "login": f.url_for("api.login", _external=True),
                "logout": f.url_for("api.logout", _external=True),
                "info": f.url_for("api.infos", _external=True),
                "hardware": f.url_for("api.hardwares", _external=True),
                "ping": f.url_for("api.ping", _external=True),
                "register": f.url_for("api.register", _external=True),
                "runs": f.url_for("api.runs", _external=True),
                "users": f.url_for("api.users", _external=True),
            }
        }


class IndexAPI(ApiEndpoint):
    serializer = IndexSerializer()

    @flask_login.login_required
    def get(self):
        """
        ---
        description: Get a list of API endpoints.
        responses:
            "200": "Index"
            "401": "401"
        tags:
          - Index
        """
        return self.serializer.dump()


class PingSchema(marshmallow.Schema):
    date = marshmallow.fields.DateTime(
        metadata={"description": "Current date & time"}, required=True
    )


class PingAPI(ApiEndpoint):
    def get(self):
        """
        ---
        description: Ping the API for status monitoring.
        responses:
            "200": "Ping"
        tags:
          - Ping
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        query = text("SELECT version_num FROM alembic_version")
        try:
            # In local deployment the PostgreSQL server logs: `ERROR:  relation
            # "alembic_version" does not exist at character 25`. That is
            # probably because not schema migration has yet been performed?
            # Should we make it so that this table exists also for those
            # dev/from-scratch deployments?
            version = list(Session.execute(query))[0]["version_num"]
        except:
            version = "unknown"
        return {
            "date": now.strftime("%a, %d %b %Y %H:%M:%S %Z"),
            "conbench_version": __version__,
            "alembic_version": version,
        }


def register_api(view, endpoint, url):
    view_func = view.as_view(endpoint)
    rule(url, view_func=view_func, methods=["GET"])


register_api(PingAPI, "ping", "/ping/")
register_api(IndexAPI, "index", "/")
spec.components.schema("Ping", schema=PingSchema)
