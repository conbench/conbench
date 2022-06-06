import flask as f

from .. import __version__
from ..app import rule
from ..app._endpoint import AppEndpoint
from ..app.benchmarks import RunMixin
from ..config import Config


class Index(AppEndpoint, RunMixin):
    def page(self, runs):
        return self.render_template(
            "index.html",
            application=Config.APPLICATION_NAME,
            title="Home",
            version=__version__,
            runs=runs,
            search_value=f.request.args.get("search"),
        )

    def get(self):
        if self.public_data_off():
            return self.redirect("app.login")

        runs = self.get_display_runs()
        return self.page(runs)


view = Index.as_view("index")
rule("/", view_func=view, methods=["GET"])
rule("/index/", view_func=view, methods=["GET"])
