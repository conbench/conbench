import logging
from typing import Optional

import bokeh
import flask as f
import flask_login
import flask_wtf
import wtforms as w

import conbench.util

from ..app import rule
from ..app._endpoint import AppEndpoint, authorize_or_terminate
from ..app._plots import TimeSeriesPlotMixin
from ..app._util import augment, display_time
from ..config import Config

log = logging.getLogger(__name__)


class BenchmarkResultUpdateForm(flask_wtf.FlaskForm):
    title = conbench.util.dedent_rejoin(
        """
        This applies (only) to the rolling window z-score change detection
        method indicated in the plot above.

        Use this to annotate an expected, significant change of benchmarking
        results from this point onwards. The annotation is persisted in the
        Conbench database (but can be removed again by authorized users like
        yourself).

        Specifically, this resets the rolling window mean value calculation
        ("forget the past, all of it!"). The rolling window standard deviation
        calculation is not affected. Think: the standard deviation is used to
        measure spread, and then the current mean is where that spread is
        centered. More about the rolling window z-score method can be found in
        the documentation at [TODO].
        """
    )
    toggle_distribution_change = w.SubmitField(render_kw={"title": title})


class BenchmarkResultDeleteForm(flask_wtf.FlaskForm):
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


class BenchmarkResultMixin:
    def get_display_benchmark(self, benchmark_id):
        # this gets a benchmark _result_, we need more renaming.
        benchmark, response = self._get_benchmark(benchmark_id)

        if response.status_code == 404:
            self.flash(f"unknown benchmark result ID: {benchmark_id}", "info")

        if response.status_code != 200:
            # Note(JP): quick band-aid to at least not swallow err detail, need
            # to do better err handling
            log.info(
                "get_display_benchmark(): internal api resp with code %s: %s",
                response.status_code,
                response.text,
            )
            self.flash("Error getting benchmark", "info")
            return None

        augment(benchmark)
        context = self._get_context(benchmark)
        context.pop("links", None)
        benchmark["context"] = context
        info = self._get_info(benchmark)
        info.pop("links", None)
        benchmark["info"] = info

        return benchmark

    # this gets a benchmark result, we need more renaming.
    def _get_benchmark(self, benchmark_id):
        # TODO: remove re-serialization indirection.
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
    def get_display_run(self, run_id) -> Optional[dict]:
        run, response = self._get_run(run_id)

        if response.status_code == 404:
            self.flash(f"Run ID unknown: {run_id}", "info")  # type: ignore
            return None

        if response.status_code != 200:
            log.warning(
                "virtual http request failed. response: %s, %s",
                response.status_code,
                response.text,
            )
            self.flash(f"Error getting run with ID: {run_id}")  # type: ignore
            return None

        self._augment(run)
        return run

    def get_display_baseline_run(self, run_url):
        run, response = self._get_run_by_url(run_url)
        if response.status_code != 200:
            # "RunMixin" has no attribute "flash"
            self.flash("Error getting run.")  # type: ignore
            return None

        self._augment(run)
        return run

    def get_display_runs(self):
        runs, response = self._get_runs()
        if response.status_code != 200:
            self.flash("Error getting runs.")  # type: ignore
            return []

        for run in runs:
            self._augment(run)
        return runs

    def _augment(self, run):
        self._display_time(run, "timestamp")

        # Note(JP): `run["commit"]["timestamp"]` can be `None`, see
        # https://github.com/conbench/conbench/pull/651
        # Does run["commit"] every result in KeyError?
        self._display_time(run["commit"], "timestamp")
        repository = run["commit"]["repository"]
        repository_name = repository

        if "github.com/" in repository:
            repository_name = repository.split("github.com/")[1]

        run["display_name"] = ""
        if run["name"]:
            run["display_name"] = run["name"].split(":", 1)[0]

        run["commit"]["display_repository"] = repository_name

        # For HTML template processing make it so that the commit dictionary
        # _always_ has non-empty string value for all of the following
        # properties:
        # - "url"
        # - "display_message"
        # - "html_commit_anchor_and_msg"
        #
        # Expect the "sha" key to be present as a non-empty strings

        c = run["commit"]
        if c.get("url") is None:
            # non-empty string value for HTML
            c["url"] = "#"

        # Assume that run["commit"]["message"] never results in KeyError.
        # (we will see).
        short_commit_message = conbench.util.short_commit_msg(c["message"])
        commit_anchor_text = c["sha"][:7]
        commit_html_anchor_and_msg = f'<a href="{c["url"]}">{commit_anchor_text}</a> <code>({short_commit_message})</code>'

        c["display_message"] = short_commit_message
        c["html_anchor_and_msg"] = commit_html_anchor_and_msg

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


class BenchmarkResult(AppEndpoint, BenchmarkResultMixin, RunMixin, TimeSeriesPlotMixin):
    def page(self, benchmark, run, delete_form, update_form):
        if benchmark is None:
            return self.redirect("app.index")

        update_button_color = "secondary"
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

        plotinfo = self.get_history_plot(benchmark, run)

        return self.render_template(
            "benchmark-result.html",
            application=Config.APPLICATION_NAME,
            title="Benchmark",
            benchmark=benchmark,
            run=run,
            delete_form=delete_form,
            update_form=update_form,
            resources=bokeh.resources.CDN.render(),
            history_plot_info=plotinfo,
            update_button_color=update_button_color,
        )

    @authorize_or_terminate
    def get(self, benchmark_id):
        benchmark, run = self._get_benchmark_and_run(benchmark_id)
        return self.page(
            benchmark, run, BenchmarkResultDeleteForm(), BenchmarkResultUpdateForm()
        )

    def post(self, benchmark_id):
        if not flask_login.current_user.is_authenticated:
            return self.redirect("app.login")

        delete_form, delete_response = BenchmarkResultDeleteForm(), None
        update_form, update_response = BenchmarkResultUpdateForm(), None

        if delete_form.delete.data:
            # delete button pressed
            if delete_form.validate_on_submit():
                delete_response = self.api_delete(
                    "api.benchmark", benchmark_id=benchmark_id
                )
                if delete_response.status_code == 204:
                    self.flash(f"Benchmark result {benchmark_id} deleted.", "info")
                    return self.redirect("app.benchmark-results")

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

    def data(self, form: BenchmarkResultUpdateForm):
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


class BenchmarkResultList(AppEndpoint, ContextMixin):
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
            delete_benchmark_form=BenchmarkResultDeleteForm(),
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
    "/benchmark-results/",
    view_func=BenchmarkResultList.as_view("benchmark-results"),
    methods=["GET"],
)

rule(
    "/benchmark-results/<benchmark_id>/",
    view_func=BenchmarkResult.as_view("benchmark-result"),
    methods=["GET", "POST"],
)


# Legacy route, which people have used to communicate a URL e.g. via Slack or
# email, or in downstream reporting, to point to a specific benchmark result
# view. Keep this working _in addition to_ the new, more descriptive
# `/benchmark-results/<benchmark_id>/` path. Keep this working for as long as
# we can do so with ease. Next step for this outstretched transition might be
# to build custom logic that would act on the shape of <benchmark_id> and emit
# a redirect response. Note that this needs a different name argument passed to
# the as_view() method, otherwise one sees an error like `View function mapping
# is overwriting an existing endpoint function: app.benchmark`
# Context: https://github.com/conbench/conbench/pull/966#issuecomment-1487072612
rule(
    "/benchmarks/<benchmark_id>/",
    view_func=BenchmarkResult.as_view("benchmark"),
    methods=["GET", "POST"],
)
