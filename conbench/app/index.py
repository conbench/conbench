import flask as f

from .. import __version__
from ..app import rule
from ..app._endpoint import AppEndpoint, authorize_or_terminate
from ..app.benchmarks import RunMixin
from ..buildinfo import BUILD_INFO
from ..config import Config

# Default to importlib_metadata version string.
VERSION_STRING_FOOTER = __version__


# Enrich with short commit hash, if available.
# Also see https://github.com/conbench/conbench/issues/461
if BUILD_INFO is not None:
    VERSION_STRING_FOOTER = f"{__version__}-{BUILD_INFO.commit[:9]}"


class Index(AppEndpoint, RunMixin):
    def page(self, runs):
        return self.render_template(
            "index.html",
            application=Config.APPLICATION_NAME,
            title="Home",
            version_string_footer=VERSION_STRING_FOOTER,
            runs=runs,
            search_value=f.request.args.get("search"),
        )

    @authorize_or_terminate
    def get(self):
        runs = self.get_display_runs()
        return self.page(runs)


view = Index.as_view("index")
rule("/", view_func=view, methods=["GET"])
rule("/index/", view_func=view, methods=["GET"])
