import dataclasses
from typing import Dict

import bokeh
import flask as f
import flask_login
import flask_wtf
import wtforms as w

from ..app import rule
from ..app._endpoint import AppEndpoint, authorize_or_terminate
from ..app._plots import TimeSeriesPlotMixin
from ..app._util import augment
from ..app.results import ContextMixin, RunMixin
from ..config import Config


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
            return '<span class="badge bg-primary">Recommended</span>'
        else:
            return ""


_default_hyperlink_text = {
    "parent": "compare to baseline run from parent commit",
    "fork_point": "compare to baseline run from fork point commit",
    "latest_default": "compare to latest comparable baseline run on default branch",
}


# This class had the same name as `entities.Run`. Mypy got confused:
#   conbench/app/__init__.py:16: error: Incompatible import of "Run"
#   (imported name has type "Type[conbench.app.runs.Run]", local name has
#     type "Type[conbench.entities.run.Run]")  [assignment]
class ViewRun(AppEndpoint, ContextMixin, RunMixin, TimeSeriesPlotMixin):
    def page(self, benchmarks, contender_run, form, run_id):
        if not flask_login.current_user.is_authenticated:
            delattr(form, "delete")

        # For each candidate baseline type, if a baseline run exists for this contender
        # run, store information to fill in the HTML hyperlink for that comparison.
        comparison_info: Dict[str, _RunComparisonLinker] = {}
        if contender_run:
            for key in ["parent", "fork_point", "latest_default"]:
                baseline_id = contender_run["candidate_baseline_runs"][key][
                    "baseline_run_id"
                ]
                if baseline_id:
                    comparison_info[key] = _RunComparisonLinker(
                        url=f.url_for(
                            "app.compare-runs",
                            compare_ids=f"{baseline_id}...{contender_run['id']}",
                        ),
                        text=_default_hyperlink_text[key],
                        recommended=False,
                    )

        if len(comparison_info) > 1:
            # Figure out which baseline is "recommended".
            # (The run will definitely have a commit in this case.)
            if (
                contender_run["commit"]["sha"]
                == contender_run["commit"]["fork_point_sha"]
            ):
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

        # (
        #     biggest_changes,
        #     biggest_changes_ids,
        #     biggest_changes_names,
        # ) = self.get_biggest_changes(benchmarks)

        # plot_history = [
        #     self.get_history_plot(b, contender_run, i)
        #     for i, b in enumerate(biggest_changes)
        # ]

        return self.render_template(
            "run.html",
            application=Config.APPLICATION_NAME,
            title="Run",
            benchmarks=benchmarks,
            comparisons=sorted(
                comparison_info.values(), key=lambda x: x.recommended, reverse=True
            ),
            run_id=run_id,
            run=contender_run,
            form=form,
            resources=bokeh.resources.CDN.render(),
            # plot_history=plot_history,
            # outlier_names=biggest_changes_names,
            # outlier_ids=biggest_changes_ids,
            search_value=f.request.args.get("search"),
        )

    @authorize_or_terminate
    def get(self, run_id):
        contender_run = self.get_display_run(run_id)
        benchmarks, response = self._get_benchmarks(run_id)
        if response.status_code != 200:
            self.flash("Error getting benchmarks.")
            return self.redirect("app.index")

        contexts = self.get_contexts(benchmarks)
        for benchmark in benchmarks:
            augment(benchmark, contexts)

        return self.page(benchmarks, contender_run, DeleteForm(), run_id)

    def _get_benchmarks(self, run_id):
        response = self.api_get("api.benchmarks", run_id=run_id)
        return response.json, response

    def post(self, run_id):
        if not flask_login.current_user.is_authenticated:
            return self.redirect("app.login")
        form, response = DeleteForm(), None
        if form.delete.data:
            if form.validate_on_submit():
                response = self.api_delete(
                    "api.run",
                    run_id=run_id,
                )
                if response.status_code == 204:
                    self.flash("Run deleted.")
                else:
                    self.flash("Error deleting run.")
        csrf = {"csrf_token": ["The CSRF token is missing."]}
        if form.errors == csrf:
            self.flash("The CSRF token is missing.")
        return self.redirect("app.index")


class DeleteForm(flask_wtf.FlaskForm):
    delete = w.SubmitField("Delete")


rule(
    "/runs/<run_id>/",
    view_func=ViewRun.as_view("run"),
    methods=["GET", "POST"],
)
