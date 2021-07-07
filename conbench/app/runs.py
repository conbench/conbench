import flask as f

from ..app import rule
from ..app._endpoint import AppEndpoint
from ..app._util import augment
from ..app.benchmarks import ContextMixin, RunMixin
from ..config import Config


class RunPlot(AppEndpoint, ContextMixin, RunMixin):
    def page(self, benchmarks, baseline_run, contender_run):
        compare_runs_url = None
        if baseline_run and contender_run:
            compare = f'{baseline_run["id"]}...{contender_run["id"]}'
            compare_runs_url = f.url_for("app.compare-runs", compare_ids=compare)

        return self.render_template(
            "run.html",
            application=Config.APPLICATION_NAME,
            title="Run",
            benchmarks=benchmarks,
            compare_runs_url=compare_runs_url,
        )

    def get(self, run_id):
        contender_run, baseline_run = self.get_display_run(run_id), None
        if contender_run:
            baseline_url = contender_run["links"].get("baseline")
            if baseline_url:
                baseline_run = self.get_display_baseline_run(baseline_url)

        benchmarks, response = self._get_benchmarks(run_id)
        contexts = self.get_contexts(benchmarks)
        if response.status_code != 200:
            self.flash("Error getting benchmarks.")
            return self.redirect("app.index")

        for benchmark in benchmarks:
            augment(benchmark, contexts)

        return self.page(benchmarks, baseline_run, contender_run)

    def _get_benchmarks(self, run_id):
        response = self.api_get("api.benchmarks", run_id=run_id)
        return response.json, response


rule(
    "/runs/<run_id>/",
    view_func=RunPlot.as_view("run"),
    methods=["GET"],
)
