import dataclasses
from typing import Dict, List

import bokeh
import flask as f
from sqlalchemy import select

from ..app import rule
from ..app._endpoint import AppEndpoint, authorize_or_terminate
from ..app._plots import TimeSeriesPlotMixin
from ..app._util import augment, error_page
from ..app.results import ContextMixin, RunMixin
from ..config import Config
from ..dbsession import current_session
from ..entities.benchmark_result import BenchmarkResult


@dataclasses.dataclass
class _RunComparisonLinker:
    # URL comparing the contender run to the baseline run.
    url: str
    # Display text to hyperlink the URL.
    text: str
    # Whether this is the "recommended" baseline run.
    recommended: bool

    @property
    def badge(self) -> str:
        if self.recommended:
            return "recommended"
        else:
            return ""


_default_hyperlink_text = {
    "parent": "compare to baseline run from parent commit",
    "fork_point": "compare to baseline run from fork point commit",
    "latest_default": "compare to latest comparable baseline run on default branch",
}


class ViewRun(AppEndpoint, ContextMixin, RunMixin, TimeSeriesPlotMixin):
    def page(self, benchmark_results, rundict):
        # For each candidate baseline type, if a baseline run exists for this contender
        # run, store information to fill in the HTML hyperlink for that comparison.
        comparison_info: Dict[str, _RunComparisonLinker] = {}

        # Why would that ever be called without rundict being defined?
        if rundict:
            for key in ["parent", "fork_point", "latest_default"]:
                baseline_id = rundict["candidate_baseline_runs"][key]["baseline_run_id"]
                if baseline_id:
                    comparison_info[key] = _RunComparisonLinker(
                        url=f.url_for(
                            "app.compare-runs",
                            compare_ids=f"{baseline_id}...{rundict['id']}",
                        ),
                        text=_default_hyperlink_text[key],
                        recommended=False,
                    )

        if len(comparison_info) > 1:
            # Figure out which baseline is "recommended".
            # (The run will definitely have a commit in this case.)
            if rundict["commit"]["sha"] == rundict["commit"]["fork_point_sha"]:
                # On the default branch, so the parent run is recommended.
                comparison_info["parent"].recommended = True
            elif "fork_point" in comparison_info:
                # On a non-default branch, so the fork point run is recommended.
                comparison_info["fork_point"].recommended = True
            else:
                # On a non-default branch with an error finding the fork point baseline
                # run, so the latest default run is recommended. I can't think of any
                # feasible scenario where this might happen but it's important not to
                # error out just trying to display a word.
                comparison_info["latest_default"].recommended = True

        return self.render_template(
            "run.html",
            application=Config.APPLICATION_NAME,
            title="Run",
            benchmarks=benchmark_results,
            comparisons=sorted(
                comparison_info.values(), key=lambda x: x.recommended, reverse=True
            ),
            run=rundict,
            resources=bokeh.resources.CDN.render(),
        )

    @authorize_or_terminate
    def get(self, run_id):
        rundict = self.get_display_run(run_id)

        if rundict is None:
            # Rely on get_display_run to have set flash msg state (err msg for
            # user). Show that msg by rendering the err page templ
            return error_page()

        benchmark_results = self._get_results(run_id)

        contexts = self.get_contexts(benchmark_results)
        for r in benchmark_results:
            augment(r, contexts)

        return self.page(benchmark_results, rundict)

    def _get_results(self, run_id) -> List[dict]:
        query = select(BenchmarkResult).filter(BenchmarkResult.run_id == run_id)
        return [r.to_dict_for_json_api() for r in current_session.scalars(query).all()]


rule(
    "/runs/<run_id>/",
    view_func=ViewRun.as_view("run"),
    methods=["GET"],
)
