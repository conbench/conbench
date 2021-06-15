import flask_login
import flask_wtf
import wtforms as w

from ..app import rule
from ..app._endpoint import AppEndpoint
from ..app._util import augment, display_time
from ..config import Config


class DeleteForm(flask_wtf.FlaskForm):
    delete = w.SubmitField("Delete")


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
        self._display_time(run["commit"], "timestamp")
        repository = run["commit"]["repository"]
        repository_name = repository.split("github.com/")[1]
        run["commit"]["display_repository"] = repository_name

    def _display_time(self, obj, field):
        obj[f"display_{field}"] = display_time(obj[field])

    def _get_run(self, run_id):
        response = self.api_get("api.run", run_id=run_id)
        return response.json, response

    def _get_run_by_url(self, run_url):
        response = self.api_get_url(run_url)
        return response.json, response

    def _get_runs(self):
        response = self.api_get("api.runs")
        return response.json, response


class Benchmark(AppEndpoint, BenchmarkMixin, RunMixin):
    def page(self, benchmark, run, form):
        if not flask_login.current_user.is_authenticated:
            delattr(form, "delete")

        if benchmark is None:
            return self.redirect("app.index")

        return self.render_template(
            "benchmark-entity.html",
            application=Config.APPLICATION_NAME,
            title="Benchmark",
            benchmark=benchmark,
            run=run,
            form=form,
        )

    def get(self, benchmark_id):
        benchmark, run = self._get_benchmark_and_run(benchmark_id)
        return self.page(benchmark, run, DeleteForm())

    def post(self, benchmark_id):
        if not flask_login.current_user.is_authenticated:
            return self.redirect("app.login")

        form, response = DeleteForm(), None

        if form.delete.data:
            # delete button pressed
            if form.validate_on_submit():
                response = self.api_delete(
                    "api.benchmark",
                    benchmark_id=benchmark_id,
                )
                if response.status_code == 204:
                    self.flash("Benchmark deleted.")
                    return self.redirect("app.benchmarks")

        if response and not form.errors:
            self.flash(response.json["name"])

        csrf = {"csrf_token": ["The CSRF token is missing."]}
        if form.errors == csrf:
            self.flash("The CSRF token is missing.")

        benchmark, run = self._get_benchmark_and_run(benchmark_id)
        return self.page(benchmark, run, form)

    def _get_benchmark_and_run(self, benchmark_id):
        benchmark = self.get_display_benchmark(benchmark_id)
        run = None
        if benchmark is not None:
            run_id = benchmark["stats"]["run_id"]
            run = self.get_display_run(run_id)
        return benchmark, run


class BenchmarkList(AppEndpoint):
    def page(self, benchmarks):
        for benchmark in benchmarks:
            augment(benchmark)

        return self.render_template(
            "benchmark-list.html",
            application=Config.APPLICATION_NAME,
            title="Benchmarks",
            benchmarks=benchmarks,
            delete_benchmark_form=DeleteForm(),
        )

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
