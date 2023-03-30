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


# This class had the same name as `entities.Run`. Mypy got confused:
#   conbench/app/__init__.py:16: error: Incompatible import of "Run"
#   (imported name has type "Type[conbench.app.runs.Run]", local name has
#     type "Type[conbench.entities.run.Run]")  [assignment]
class ViewRun(AppEndpoint, ContextMixin, RunMixin, TimeSeriesPlotMixin):
    def page(self, benchmarks, baseline_run, contender_run, form, run_id):
        compare_runs_url = None
        if not flask_login.current_user.is_authenticated:
            delattr(form, "delete")
        if baseline_run and contender_run:
            compare = f'{baseline_run["id"]}...{contender_run["id"]}'
            compare_runs_url = f.url_for("app.compare-runs", compare_ids=compare)

        (
            biggest_changes,
            biggest_changes_ids,
            biggest_changes_names,
        ) = self.get_biggest_changes(benchmarks)
        plot_history = [
            self.get_history_plot(b, contender_run, i)
            for i, b in enumerate(biggest_changes)
        ]

        return self.render_template(
            "run.html",
            application=Config.APPLICATION_NAME,
            title="Run",
            benchmarks=benchmarks,
            compare_runs_url=compare_runs_url,
            run_id=run_id,
            run=contender_run,
            form=form,
            resources=bokeh.resources.CDN.render(),
            plot_history=plot_history,
            outlier_names=biggest_changes_names,
            outlier_ids=biggest_changes_ids,
            search_value=f.request.args.get("search"),
        )

    @authorize_or_terminate
    def get(self, run_id):
        contender_run, baseline_run = self.get_display_run(run_id), None
        if contender_run:
            baseline_url = contender_run["links"].get("baseline")
            if baseline_url:
                baseline_run = self.get_display_baseline_run(baseline_url)

        benchmarks, response = self._get_benchmarks(run_id)
        if response.status_code != 200:
            self.flash("Error getting benchmarks.")
            return self.redirect("app.index")

        contexts = self.get_contexts(benchmarks)
        for benchmark in benchmarks:
            augment(benchmark, contexts)

        return self.page(benchmarks, baseline_run, contender_run, DeleteForm(), run_id)

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
