from ..app import rule
from ..app._endpoint import AppEndpoint
from ..app.benchmarks import RunMixin
from ..config import Config

# set the version
try:
    import importlib.metadata as importlib_metadata
except ImportError:
    # TODO: remove this when Python 3.7 support is dropped
    import importlib_metadata

try:
    __version__ = importlib_metadata.version(__name__)
except Exception:
    __version__ = importlib_metadata.version("conbench")

del importlib_metadata


class Index(AppEndpoint, RunMixin):
    def page(self, runs):
        reasons = {r["display_name"] for r in runs if r["display_name"]}
        commits = {r["commit"]["url"] for r in runs if r["commit"]["url"]}
        authors = {
            r["commit"]["author_name"] for r in runs if r["commit"]["author_name"]
        }
        return self.render_template(
            "index.html",
            application=Config.APPLICATION_NAME,
            title="Home",
            version=__version__,
            runs=runs,
            has_reasons=len(reasons) > 0,
            has_authors=len(authors) > 0,
            has_commits=len(commits) > 0,
        )

    def get(self):
        if self.public_data_off():
            return self.redirect("app.login")

        runs = self.get_display_runs()
        return self.page(runs)


view = Index.as_view("index")
rule("/", view_func=view, methods=["GET"])
rule("/index/", view_func=view, methods=["GET"])
