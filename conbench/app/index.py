from ..app import rule
from ..app._endpoint import AppEndpoint
from ..app.benchmarks import RunMixin
from ..config import Config


class Index(AppEndpoint, RunMixin):
    def page(self, runs):
        reasons = {r["name"].split(":", 1)[0] for r in runs if r["name"]}
        authors = {
            r["commit"]["author_name"] for r in runs if r["commit"]["author_name"]
        }
        return self.render_template(
            "index.html",
            application=Config.APPLICATION_NAME,
            title="Home",
            runs=runs,
            has_reasons=len(reasons) > 0,
            has_authors=len(authors) > 0,
        )

    def get(self):
        runs = self.get_display_runs()
        return self.page(runs)


view = Index.as_view("index")
rule("/", view_func=view, methods=["GET"])
rule("/index/", view_func=view, methods=["GET"])
