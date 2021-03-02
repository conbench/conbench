from ..app import rule
from ..app._endpoint import AppEndpoint
from ..app._util import augment
from ..config import Config


class RunPlot(AppEndpoint):
    def page(self, benchmarks):
        return self.render_template(
            "run.html",
            application=Config.APPLICATION_NAME,
            title="Run",
            benchmarks=benchmarks,
        )

    def get(self, run_id):
        benchmarks, response = self._get_benchmarks(run_id)
        if response.status_code != 200:
            self.flash("Error getting benchmarks.")
            return self.redirect("app.index")

        for benchmark in benchmarks:
            augment(benchmark)

        return self.page(benchmarks)

    def _get_benchmarks(self, run_id):
        response = self.api_get("api.benchmarks", run_id=run_id)
        return response.json, response


rule(
    "/runs/<run_id>/",
    view_func=RunPlot.as_view("run"),
    methods=["GET"],
)
