import copy
import flask as f
import json

import bokeh

from ..app import rule
from ..app._endpoint import AppEndpoint
from ..app._plots import simple_bar_plot
from ..app.benchmarks import BenchmarkMixin
from ..config import Config


class Compare(AppEndpoint, BenchmarkMixin):
    def page(self, comparisons, baseline_id, contender_id):

        unknown = f"unknown...unknown"
        compare_runs_url = f.url_for("app.compare-runs", compare_ids=unknown)
        compare_batches_url = f.url_for("app.compare-batches", compare_ids=unknown)
        baseline, contender, plot = None, None, None

        if comparisons and self.type == "batch":
            baseline_run_id = comparisons[0]["baseline_run_id"]
            contender_run_id = comparisons[0]["contender_run_id"]
            compare = f"{baseline_run_id}...{contender_run_id}"
            compare_runs_url = f.url_for("app.compare-runs", compare_ids=compare)
        elif comparisons and self.type == "benchmark":
            baseline = self._get_full_benchmark(baseline_id)
            contender = self._get_full_benchmark(contender_id)
            plot = self._get_plot(baseline, contender)
            b_stats, c_stats = baseline["stats"], contender["stats"]
            compare = f'{b_stats["run_id"]}...{c_stats["run_id"]}'
            compare_runs_url = f.url_for("app.compare-runs", compare_ids=compare)
            compare = f'{b_stats["batch_id"]}...{c_stats["batch_id"]}'
            compare_batches_url = f.url_for("app.compare-batches", compare_ids=compare)

        return self.render_template(
            self.html,
            application=Config.APPLICATION_NAME,
            title=self.title,
            type=self.type,
            plot=plot,
            resources=bokeh.resources.CDN.render(),
            comparisons=comparisons,
            contender_id=contender_id,
            baseline_id=baseline_id,
            contender=contender,
            baseline=baseline,
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
                f"plot",
            ),
        )
        return plot

    def get(self, compare_ids):
        threshold = f.request.args.get("threshold")
        params = {"compare_ids": compare_ids}
        if threshold is not None:
            params["threshold"] = threshold

        try:
            baseline_id, contender_id = compare_ids.split("...", 1)
            comparisons = self._compare(params)
            if not comparisons:
                self.flash("Data is still collecting (or failed).")
        except ValueError:
            baseline_id, contender_id = "unknown", "unknown"
            comparisons = []
            self.flash("Invalid contender and baseline.")

        return self.page(comparisons, baseline_id, contender_id)

    def _compare(self, params):
        response = self.api_get(self.api, **params)

        comparisons = []
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

                c["change"] = float(c["change"][:-1])
                if c["less_is_better"]:
                    c["change"] = c["change"] * -1

        return comparisons


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
