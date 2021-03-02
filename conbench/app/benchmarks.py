import flask_login
import flask_wtf
import wtforms as w

from ..app import rule
from ..app._endpoint import AppEndpoint
from ..app._util import augment
from ..config import Config


class DeleteForm(flask_wtf.FlaskForm):
    delete = w.SubmitField("Delete")


class BenchmarkMixin:
    def _get_full_benchmark(self, benchmark_id):
        response = self.api_get("api.benchmark", benchmark_id=benchmark_id)
        benchmark = response.json

        if response.status_code != 200:
            self.flash("Error getting benchmark.")
            return None

        augment(benchmark)
        machine = self._get_machine(benchmark)
        context = self._get_context(benchmark)
        machine.pop("links", None)
        context.pop("links", None)
        benchmark["machine"] = machine
        benchmark["context"] = context

        return benchmark

    def _get_context(self, benchmark):
        response = self.api_get_url(benchmark["links"]["context"])
        if response.status_code != 200:
            self.flash("Error getting context.")
            return {}
        return response.json

    def _get_machine(self, benchmark):
        response = self.api_get_url(benchmark["links"]["machine"])
        if response.status_code != 200:
            self.flash("Error getting machine.")
            return {}
        return response.json


class Benchmark(AppEndpoint, BenchmarkMixin):
    def page(self, benchmark, form):
        if not flask_login.current_user.is_authenticated:
            delattr(form, "delete")

        if benchmark is None:
            return self.redirect("app.index")

        return self.render_template(
            "benchmark-entity.html",
            application=Config.APPLICATION_NAME,
            title="Benchmark",
            benchmark=benchmark,
            form=form,
        )

    def get(self, benchmark_id):
        benchmark = self._get_full_benchmark(benchmark_id)
        return self.page(benchmark, DeleteForm())

    def post(self, benchmark_id):
        if not flask_login.current_user.is_authenticated:
            return self.redirect("app.login")

        form, response = DeleteForm(), None

        if form.delete.data:
            # delete button pressed
            if form.validate_on_submit():
                response = self.api_delete("api.benchmark", benchmark_id=benchmark_id)
                if response.status_code == 204:
                    self.flash("Benchmark deleted.")
                    return self.redirect("app.benchmarks")

        if response and not form.errors:
            self.flash(response.json["name"])

        csrf = {"csrf_token": ["The CSRF token is missing."]}
        if form.errors == csrf:
            self.flash("The CSRF token is missing.")

        benchmark = self._get_full_benchmark(benchmark_id)
        return self.page(benchmark, form)


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
