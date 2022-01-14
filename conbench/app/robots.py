import flask as f

from ..app import rule
from ..app._endpoint import AppEndpoint

text = """
User-Agent: *
Disallow: /
"""


class Robots(AppEndpoint):
    def get(self):
        response = f.Response(
            response=text,
            status=200,
            mimetype="text/plain",
        )
        response.headers["Content-Type"] = "text/plain; charset=utf-8"
        return response


rule(
    "/robots.txt",
    view_func=Robots.as_view("robots"),
    methods=["GET"],
)
