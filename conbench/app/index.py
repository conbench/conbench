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
            runs=runs,
        )

    def get(self):
        runs = self.get_display_runs()
        return self.page(runs)


view = Index.as_view("index")
rule("/", view_func=view, methods=["GET"])
rule("/index/", view_func=view, methods=["GET"])
