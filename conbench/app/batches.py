import collections
import json

import bokeh
import flask as f

from ..app import rule
from ..app._endpoint import AppEndpoint, authorize_or_terminate
from ..app._plots import simple_bar_plot
from ..app._util import augment
from ..app.results import ContextMixin
from ..config import Config


class BatchPlot(AppEndpoint, ContextMixin):
    def page(self, by_group, requested_batch_id):
        plots, raw, i = [], [], 1
        for benchmarks in by_group.values():
            raw.extend(benchmarks)
            for p in [simple_bar_plot(benchmarks, height=400, width=700)]:
                if p:
                    plot = json.dumps(bokeh.embed.json_item(p, f"plot{i}"))
                    plots.append(plot)
                    i += 1

        return self.render_template(
            "batch.html",
            application=Config.APPLICATION_NAME,
            title="Batch",
            resources=bokeh.resources.CDN.render(),
            # Note(JP): `raw` seems to be the ungrouped list of benchmarks as
            # obtained below via `self._get_benchmarks(batch_id)`
            benchmarks=raw,
            plots=plots,
            search_value=f.request.args.get("search"),
            requested_batch_id=requested_batch_id,
        )

    @authorize_or_terminate
    def get(self, batch_id):
        benchmarks, response = self._get_benchmarks(batch_id)
        if response.status_code != 200:
            self.flash("Error getting benchmarks.")
            return self.redirect("app.index")

        group_by_key = "dataset"  # TODO: move to GRAPHS
        by_group = collections.defaultdict(list)
        contexts = self.get_contexts(benchmarks)
        for benchmark in benchmarks:
            # Note(JP): This, among others, sets
            #
            #   benchmark["display_batch"] = batch
            #
            # whereas `batch` here is not the batch_id, but a per-benchmark
            # result (suite) name derived from benchmark result tags
            augment(benchmark, contexts)
            tags = benchmark["tags"]
            key = f'{tags["name"]}-{tags.get(group_by_key, "")}'
            by_group[key].append(benchmark)

        return self.page(by_group, batch_id)

    def _get_benchmarks(self, batch_id):
        response = self.api_get("api.benchmarks", batch_id=batch_id)
        return response.json, response


rule(
    "/batches/<batch_id>/",
    view_func=BatchPlot.as_view("batch"),
    methods=["GET"],
)
