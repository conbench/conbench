import copy
import json

import bokeh
import flask as f

from ..app import rule
from ..app._endpoint import AppEndpoint
from ..app._plots import TimeSeriesPlotMixin, simple_bar_plot
from ..app.benchmarks import BenchmarkMixin, RunMixin
from ..config import Config


class Compare(AppEndpoint, BenchmarkMixin, RunMixin, TimeSeriesPlotMixin):
    def page(self, comparisons, regressions, improvements, baseline_id, contender_id):

        unknown = "unknown...unknown"
        compare_runs_url = f.url_for("app.compare-runs", compare_ids=unknown)
        compare_batches_url = f.url_for("app.compare-batches", compare_ids=unknown)
        baseline, contender, plot, plot_history = None, None, None, None
        baseline_run, contender_run = None, None

        if comparisons and self.type == "batch":
            ids = {c["baseline_run_id"] for c in comparisons if c["baseline_run_id"]}
            baseline_run_id = ids.pop() if ids else None
            ids = {c["contender_run_id"] for c in comparisons if c["contender_run_id"]}
            contender_run_id = ids.pop() if ids else None
            compare = f"{baseline_run_id}...{contender_run_id}"
            compare_runs_url = f.url_for("app.compare-runs", compare_ids=compare)
        elif comparisons and self.type == "run":
            baseline_run_id, contender_run_id = baseline_id, contender_id
        elif comparisons and self.type == "benchmark":
            baseline = self.get_display_benchmark(baseline_id)
            contender = self.get_display_benchmark(contender_id)
            plot = self._get_plot(baseline, contender)
            baseline_run_id = baseline["run_id"]
            contender_run_id = contender["run_id"]
            compare = f"{baseline_run_id}...{contender_run_id}"
            compare_runs_url = f.url_for("app.compare-runs", compare_ids=compare)
            compare = f'{baseline["batch_id"]}...{contender["batch_id"]}'
            compare_batches_url = f.url_for("app.compare-batches", compare_ids=compare)

        if comparisons:
            baseline_run = self.get_display_run(baseline_run_id)
            contender_run = self.get_display_run(contender_run_id)

        if comparisons and self.type == "benchmark":
            plot_history = self.get_history_plot(contender, contender_run)

        return self.render_template(
            self.html,
            application=Config.APPLICATION_NAME,
            title=self.title,
            type=self.type,
            plot=plot,
            plot_history=plot_history,
            resources=bokeh.resources.CDN.render(),
            comparisons=comparisons,
            regressions=regressions,
            improvements=improvements,
            baseline_id=baseline_id,
            contender_id=contender_id,
            baseline=baseline,
            contender=contender,
            baseline_run=baseline_run,
            contender_run=contender_run,
            compare_runs_url=compare_runs_url,
            compare_batches_url=compare_batches_url,
        )

    def _get_plot(self, baseline, contender):
        baseline_copy = copy.deepcopy(baseline)
        contender_copy = copy.deepcopy(contender)
        baseline_copy["tags"] = {
            "compare": "baseline",
            "name": baseline["display_name"],
        }
        contender_copy["tags"] = {
            "compare": "contender",
            "name": contender["display_name"],
        }
        plot = json.dumps(
            bokeh.embed.json_item(
                simple_bar_plot([baseline_copy, contender_copy], height=200),
                "plot",
            ),
        )
        return plot

    def get(self, compare_ids):
        if self.public_data_off():
            return self.redirect("app.login")

        threshold = f.request.args.get("threshold")
        params = {"compare_ids": compare_ids}
        if threshold is not None:
            params["threshold"] = threshold

        try:
            baseline_id, contender_id = compare_ids.split("...", 1)
            comparisons, regressions, improvements = self._compare(params)
            if not comparisons:
                self.flash("Data is still collecting (or failed).")
        except ValueError:
            baseline_id, contender_id = "unknown", "unknown"
            comparisons, regressions, improvements = [], None, None
            self.flash("Invalid contender and baseline.")

        return self.page(
            comparisons,
            regressions,
            improvements,
            baseline_id,
            contender_id,
        )

    def _compare(self, params):
        response = self.api_get(self.api, **params)

        comparisons, regressions, improvements = [], 0, 0
        if response.status_code == 200:
            comparisons = [response.json]
            if isinstance(response.json, list):
                comparisons = response.json

            for c in comparisons:
                view = "app.compare-benchmarks"
                compare = f'{c["baseline_id"]}...{c["contender_id"]}'
                c["compare_benchmarks_url"] = f.url_for(view, compare_ids=compare)

                view = "app.compare-batches"
                compare = f'{c["baseline_batch_id"]}...{c["contender_batch_id"]}'
                c["compare_batches_url"] = f.url_for(view, compare_ids=compare)

                if c["contender_z_regression"]:
                    regressions += 1
                if c["contender_z_improvement"]:
                    improvements += 1

        return comparisons, regressions, improvements


class CompareBenchmarks(Compare):
    type = "benchmark"
    html = "compare-entity.html"
    title = "Compare Benchmarks"
    api = "api.compare-benchmarks"


class CompareBatches(Compare):
    type = "batch"
    html = "compare-list.html"
    title = "Compare Batches"
    api = "api.compare-batches"


class CompareRuns(Compare):
    type = "run"
    html = "compare-list.html"
    title = "Compare Runs"
    api = "api.compare-runs"


rule(
    "/compare/benchmarks/<compare_ids>/",
    view_func=CompareBenchmarks.as_view("compare-benchmarks"),
    methods=["GET"],
)
rule(
    "/compare/batches/<compare_ids>/",
    view_func=CompareBatches.as_view("compare-batches"),
    methods=["GET"],
)
rule(
    "/compare/runs/<compare_ids>/",
    view_func=CompareRuns.as_view("compare-runs"),
    methods=["GET"],
)
