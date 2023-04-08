import copy
import json
import logging
from typing import List, Optional, Tuple

import bokeh
import flask as f

from ..app import rule
from ..app._endpoint import AppEndpoint, authorize_or_terminate
from ..app._plots import TimeSeriesPlotMixin, simple_bar_plot
from ..app._util import augment
from ..app.results import BenchmarkResultMixin, RunMixin
from ..config import Config
from ..entities.run import commit_hardware_run_map

log = logging.getLogger(__name__)


def all_keys(dict1, dict2, attr):
    if dict1 is None:
        dict1 = {}
    if dict2 is None:
        dict2 = {}
    return sorted(
        set(list(dict1.get(attr, {}).keys()) + list(dict2.get(attr, {}).keys()))
    )


class Compare(AppEndpoint, BenchmarkResultMixin, RunMixin, TimeSeriesPlotMixin):
    def page(self, comparisons, regressions, improvements, baseline_id, contender_id):
        unknown = "unknown...unknown"
        compare_runs_url = f.url_for("app.compare-runs", compare_ids=unknown)
        compare_batches_url = f.url_for("app.compare-batches", compare_ids=unknown)
        baseline, contender, plot, plot_history = None, None, None, None
        baseline_run, contender_run = None, None
        biggest_changes_names, outlier_urls = None, None

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

        if comparisons and self.type != "benchmark":
            comparisons_by_id = {c["contender_id"]: c for c in comparisons}
            if self.type == "run":
                benchmarks, response = self._get_benchmarks(run_id=contender_id)
            if self.type == "batch":
                benchmarks, response = self._get_benchmarks(batch_id=contender_id)
            if response.status_code != 200:
                self.flash("Error getting benchmarks.")
                return self.redirect("app.index")
            for benchmark in benchmarks:
                augment(benchmark)
            (
                biggest_changes,
                biggest_changes_ids,
                biggest_changes_names,
            ) = self.get_biggest_changes(benchmarks)
            outlier_urls = [
                comparisons_by_id.get(x, {}).get("compare_benchmarks_url", "")
                for x in biggest_changes_ids
            ]
            plot_history = [
                self.get_history_plot(b, contender_run, i)
                for i, b in enumerate(biggest_changes)
            ]

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
            outlier_names=biggest_changes_names,
            outlier_urls=outlier_urls,
            search_value=f.request.args.get("search"),
            tags_fields=all_keys(baseline, contender, "tags"),
            context_fields=all_keys(baseline, contender, "context"),
            info_fields=all_keys(baseline, contender, "info"),
            hardware_fields=all_keys(baseline_run, contender_run, "hardware"),
            commit_hardware_run_map=commit_hardware_run_map(),
        )

    def _get_benchmarks(self, run_id=None, batch_id=None):
        if run_id:
            response = self.api_get("api.benchmarks", run_id=run_id)
        if batch_id:
            response = self.api_get("api.benchmarks", batch_id=batch_id)
        return response.json, response

    def _get_plot(self, baseline, contender):
        baseline_copy = copy.deepcopy(baseline)
        contender_copy = copy.deepcopy(contender)
        baseline_copy["tags"] = {
            "compare": "baseline",
            "name": baseline["display_case_perm"],
        }
        contender_copy["tags"] = {
            "compare": "contender",
            "name": contender["display_case_perm"],
        }
        plot = json.dumps(
            bokeh.embed.json_item(
                simple_bar_plot(
                    [baseline_copy, contender_copy], height=200, vbar_width=0.3
                ),
                "plot",
            ),
        )
        return plot

    @authorize_or_terminate
    def get(self, compare_ids: str) -> str:
        """
        The argument `compare_ids` is an user-given unvalidated string which is
        supposed to be of the following shape:

                    <baseline_id>...<contender_id>

        Parse the shape here to provide some friendly UI feedback for common
        mistakes.

        However, for now rely on the API layer to check if these IDs are
        'known'.

        The API layer will parse the string `compare_ids` again, but that's OK
        for now.

        Note that the two IDs that are encoded `compare_ids` can be either two
        run IDs, two batch IDs or two benchmark result IDs.
        """

        if "..." not in compare_ids:
            return self.error_page(  # type: ignore
                "Got unexpected URL path pattern. Expected: <id>...<id>"
            )

        baseline_id, contender_id = compare_ids.split("...", 1)

        if not baseline_id:
            return self.error_page(  # type: ignore
                "No baseline ID was provided. Expected format: <baseline_id>...<contender_id>"
            )

        if not contender_id:
            return self.error_page(  # type: ignore
                "No contender ID was provided. Expected format: <baseline-id>...<contender-id>"
            )

        (
            comparison_results,
            regression_count,
            improvement_count,
            error_string,
        ) = self._compare(baseline_id=baseline_id, contender_id=contender_id)

        if error_string is not None:
            return self.error_page(  # type: ignore
                f"cannot perform comparison: {error_string}", alert_level="info"
            )

        if len(comparison_results) == 0:
            return self.error_page(  # type: ignore
                "comparison yielded 0 benchmark results",
                alert_level="info",
            )

        return self.page(
            comparisons=comparison_results,
            regressions=regression_count,
            improvements=improvement_count,
            baseline_id=baseline_id,
            contender_id=contender_id,
        )

    def _compare(
        self, baseline_id: str, contender_id: str
    ) -> Tuple[List, int, int, Optional[str]]:
        """
        Return a 4-tuple.

        If the last item is a string then it is an error message for why
        the comparison failed. Do not process the first three items then.
        """
        # This farms out one of three API endpoints. self.api_endpoint_name is
        # set in a child class. Re-assemble the stringified input argument for
        # the virtual API endpoint, carrying both baseline and contender ID
        params = {"compare_ids": f"{baseline_id}...{contender_id}"}
        # error: "Compare" has no attribute "api_endpoint_name"  [attr-defined]
        response = self.api_get(self.api_endpoint_name, **params)  # type: ignore

        if response.status_code != 200:
            log.error(
                "processing req to %s -- unexpected response for virtual request: %s, %s",
                f.request.url,
                response.status_code,
                response.text,
            )
            # poor-mans error propagation, until we remove the API
            # layer indirection.
            errmsg = response.text
            try:
                errmsg = response.json["description"]
            except Exception:
                pass
            return [], 0, 0, errmsg

        # below is legacy code, review for bugs and clarity
        comparisons, regressions, improvements = [], 0, 0

        comparisons = [response.json]
        if isinstance(response.json, list):
            comparisons = response.json

        # Mutate comparison objs (dictionaries) on the fly
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

        return comparisons, regressions, improvements, None


class CompareBenchmarks(Compare):
    type = "benchmark"
    html = "compare-entity.html"
    title = "Compare Benchmarks"
    api_endpoint_name = "api.compare-benchmarks"


class CompareBatches(Compare):
    type = "batch"
    html = "compare-list.html"
    title = "Compare Batches"
    api_endpoint_name = "api.compare-batches"


class CompareRuns(Compare):
    type = "run"
    html = "compare-list.html"
    title = "Compare Runs"
    api_endpoint_name = "api.compare-runs"


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
