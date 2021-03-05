from ..app import rule
from ..app._endpoint import AppEndpoint
from ..app._util import display_time
from ..config import Config


def _display_time(obj, field):
    obj[f"display_{field}"] = display_time(obj[field])


class Index(AppEndpoint):
    def page(self, runs):
        for run in runs:
            _display_time(run, "timestamp")
            _display_time(run["commit"], "timestamp")
        return self.render_template(
            "index.html",
            application=Config.APPLICATION_NAME,
            title="Home",
            runs=runs,
        )

    def get(self):
        runs, response = self._get_runs()
        if response.status_code != 200:
            self.flash("Error getting runs.")

        return self.page(runs)

    def _get_runs(self):
        response = self.api_get("api.runs")
        return response.json, response


view = Index.as_view("index")
rule("/", view_func=view, methods=["GET"])
rule("/index/", view_func=view, methods=["GET"])
