import bokeh
import flask as f
import flask_login
import flask_wtf
import wtforms as w

from ..app import rule
from ..app._endpoint import AppEndpoint, authorize_or_terminate
from ..app._plots import TimeSeriesPlotMixin
from ..app._util import augment, display_message, display_time
from ..config import Config


class UpdateForm(flask_wtf.FlaskForm):
    toggle_distribution_change = w.SubmitField(
        render_kw={
            "title": 'A distribution change means a sufficiently "different" '
            "distribution began, such that data from before shouldn't be statistically "
            "compared to data after."
        }
    )


class DeleteForm(flask_wtf.FlaskForm):
    delete = w.SubmitField("Delete")


class ContextMixin:
    def get_contexts(self, benchmarks):
        context_urls, contexts = set(), {}
        for benchmark in benchmarks:
            context_urls.add(benchmark["links"]["context"])

        for context_url in context_urls:
            response = self.api_get_url(context_url)
            if response.status_code == 200:
                contexts[context_url] = response.json

        return contexts


class BenchmarkMixin:
    def get_display_benchmark(self, benchmark_id):
        benchmark, response = self._get_benchmark(benchmark_id)
        if response.status_code != 200:
            self.flash("Error getting benchmark.")
            return None

        augment(benchmark)
        context = self._get_context(benchmark)
        context.pop("links", None)
        benchmark["context"] = context
        info = self._get_info(benchmark)
        info.pop("links", None)
        benchmark["info"] = info

        return benchmark

    def _get_benchmark(self, benchmark_id):
        response = self.api_get(
            "api.benchmark",
            benchmark_id=benchmark_id,
        )
        return response.json, response

    def _get_context(self, benchmark):
        response = self.api_get_url(benchmark["links"]["context"])
        if response.status_code != 200:
            self.flash("Error getting context.")
            return {}
        return response.json

    def _get_info(self, benchmark):
        response = self.api_get_url(benchmark["links"]["info"])
        if response.status_code != 200:
            self.flash("Error getting info.")
            return {}
        return response.json


class RunMixin:
    def get_display_run(self, run_id):
        run, response = self._get_run(run_id)
        if response.status_code != 200:
            self.flash("Error getting run.")
            return None

        self._augment(run)
        return run

    def get_display_baseline_run(self, run_url):
        run, response = self._get_run_by_url(run_url)
        if response.status_code != 200:
            self.flash("Error getting run.")
            return None

        self._augment(run)
        return run

    def get_display_runs(self):
        runs, response = self._get_runs()
        if response.status_code != 200:
            self.flash("Error getting runs.")
            return []

        for run in runs:
            self._augment(run)
        return runs

    def _augment(self, run):
        self._display_time(run, "timestamp")

        # Note(JP): `run["commit"]["timestamp"]` can be `None`, see
        # https://github.com/conbench/conbench/pull/651
        self._display_time(run["commit"], "timestamp")
        repository = run["commit"]["repository"]
        repository_name = repository
        if "github.com/" in repository:
            repository_name = repository.split("github.com/")[1]
        run["display_name"] = ""
        if run["name"]:
            run["display_name"] = run["name"].split(":", 1)[0]
        run["commit"]["display_repository"] = repository_name
        commit_message = display_message(run["commit"]["message"])
        run["commit"]["display_message"] = commit_message

    def _display_time(self, obj, field):
        timestring = obj[field]

        # Seemingly this can be `None`.
        if isinstance(timestring, str):
            obj[f"display_{field}"] = display_time(timestring)

        else:
            obj[f"display_{field}"] = ""

    def _get_run(self, run_id):
        response = self.api_get("api.run", run_id=run_id)
        return response.json, response

    def _get_run_by_url(self, run_url):
        response = self.api_get_url(run_url)
        return response.json, response

    def _get_runs(self):
        response = self.api_get("api.runs")
        return response.json, response


class Benchmark(AppEndpoint, BenchmarkMixin, RunMixin, TimeSeriesPlotMixin):
    def page(self, benchmark, run, delete_form, update_form):
        if benchmark is None:
            return self.redirect("app.index")

        update_button_color = "default"
        if flask_login.current_user.is_authenticated:
            if benchmark["change_annotations"].get("begins_distribution_change", False):
                update_form.toggle_distribution_change.label.text = (
                    "Unmark this as the first result of a distribution change"
                )
                update_button_color = "info"
            else:
                update_form.toggle_distribution_change.label.text = (
                    "Mark this as the first result of a distribution change"
                )
        else:
            delattr(delete_form, "delete")
            delattr(update_form, "toggle_distribution_change")

        return self.render_template(
            "benchmark-entity.html",
            application=Config.APPLICATION_NAME,
            title="Benchmark",
            benchmark=benchmark,
            run=run,
            delete_form=delete_form,
            update_form=update_form,
            resources=bokeh.resources.CDN.render(),
            plot_history=self.get_history_plot(benchmark, run),
            update_button_color=update_button_color,
        )

    @authorize_or_terminate
    def get(self, benchmark_id):
        benchmark, run = self._get_benchmark_and_run(benchmark_id)
        return self.page(benchmark, run, DeleteForm(), UpdateForm())

    def post(self, benchmark_id):
        if not flask_login.current_user.is_authenticated:
            return self.redirect("app.login")

        delete_form, delete_response = DeleteForm(), None
        update_form, update_response = UpdateForm(), None

        if delete_form.delete.data:
            # delete button pressed
            if delete_form.validate_on_submit():
                delete_response = self.api_delete(
                    "api.benchmark", benchmark_id=benchmark_id
                )
                if delete_response.status_code == 204:
                    self.flash("Benchmark deleted.")
                    return self.redirect("app.benchmarks")

        elif update_form.validate_on_submit():
            # toggle_distribution_change button pressed
            benchmark, _ = self._get_benchmark(benchmark_id)
            update_form.toggle_distribution_change.data = benchmark[
                "change_annotations"
            ].get("begins_distribution_change", False)

            update_response = self.api_put(
                "api.benchmark", update_form, benchmark_id=benchmark_id
            )
            if update_response.status_code == 200:
                self.flash("Benchmark updated.")
                return self.get(benchmark_id=benchmark_id)

        # If the above API call didn't result in a 2XX, flash possible errors
        if delete_response and not delete_form.errors:
            self.flash(delete_response.json["name"])
        if update_response and not update_form.errors:
            self.flash(update_response.json["name"])

        csrf = {"csrf_token": ["The CSRF token is missing."]}
        if delete_form.errors == csrf or update_form.errors == csrf:
            self.flash("The CSRF token is missing.")

        benchmark, run = self._get_benchmark_and_run(benchmark_id)
        return self.page(benchmark, run, delete_form, update_form)

    def data(self, form: UpdateForm):
        """Construct the data to PUT when calling self.api_put()."""
        if form.toggle_distribution_change.data:
            return {"change_annotations": {"begins_distribution_change": False}}
        else:
            return {"change_annotations": {"begins_distribution_change": True}}

    def _get_benchmark_and_run(self, benchmark_id):
        benchmark = self.get_display_benchmark(benchmark_id)
        run = None
        if benchmark is not None:
            run = self.get_display_run(benchmark["run_id"])
        return benchmark, run


class BenchmarkList(AppEndpoint, ContextMixin):
    def page(self, benchmarks):
        # Note(JP): What type is benchmarks? As of `response =
        # self.api_get("api.benchmarks")` down below it's seemingly the result
        # of JSON-decoding, i.e. not the DB model type.
        contexts = self.get_contexts(benchmarks)
        for benchmark in benchmarks:
            augment(benchmark, contexts)

        return self.render_template(
            "benchmark-list.html",
            application=Config.APPLICATION_NAME,
            title="Benchmarks",
            benchmarks=benchmarks,
            delete_benchmark_form=DeleteForm(),
            search_value=f.request.args.get("search"),
        )

    @authorize_or_terminate
    def get(self):
        benchmarks, response = self._get_benchmarks()
        if response.status_code != 200:
            self.flash("Error getting benchmarks.")
            return self.redirect("app.index")

        return self.page(benchmarks)

    def _get_benchmarks(self):
        response = self.api_get("api.benchmarks")
        return response.json, response


rule(
    "/benchmarks/",
    view_func=BenchmarkList.as_view("benchmarks"),
    methods=["GET"],
)
rule(
    "/benchmarks/<benchmark_id>/",
    view_func=Benchmark.as_view("benchmark"),
    methods=["GET", "POST"],
)
