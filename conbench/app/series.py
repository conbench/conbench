import collections
import json

import bokeh

from ..app import rule
from ..app._endpoint import AppEndpoint
from ..app._plots import get_graph_definition, summary_scatter_plot, time_series_plot
from ..app._util import augment
from ..config import Config


def hashable(data):
    return ", ".join([f"{k}={v}" for k, v in sorted(data.items())])


class TimeSeriesPlot(AppEndpoint):
    def page(self, by_group, benchmark_name, graph):
        raw, i = [], 1
        plots = collections.defaultdict(list)
        for group_by in sorted(by_group.keys()):
            by_kind = by_group[group_by]
            for tags_hash in sorted(by_kind.keys()):
                by_machine_context = by_kind[tags_hash]
                for by_id in by_machine_context.values():
                    benchmarks = list(by_id.values())
                    raw.extend(benchmarks)
                p = time_series_plot(by_machine_context, graph)
                tags_hash = hashable(benchmarks[0]["tags"])
                if p:
                    plot = json.dumps(bokeh.embed.json_item(p, f"plot{i}"))
                    plots[group_by].append([plot, f"plot {i}", tags_hash, i])
                    i += 1

        return self.render_template(
            "series-entity.html",
            application=Config.APPLICATION_NAME,
            title="Time Series",
            benchmark_name=benchmark_name,
            resources=bokeh.resources.CDN.render(),
            benchmarks=raw,
            plots=plots,
        )

    def get(self, benchmark_name):
        benchmark_name = benchmark_name.replace("..", "/")
        benchmarks, response = self._get_benchmarks(benchmark_name)
        if response.status_code != 200:
            self.flash("Error getting benchmarks.")
            return self.redirect("app.index")

        tree = lambda: collections.defaultdict(tree)

        context_urls, machine_urls = set(), set()
        for benchmark in benchmarks:
            context_urls.add(benchmark["links"]["context"])
            machine_urls.add(benchmark["links"]["machine"])

        contexts, machines = {}, {}
        for url in context_urls:
            response = self.api_get_url(url)
            if response.status_code != 200:
                self.flash("Error getting context.")
                return self.redirect("app.index")
            context = response.json
            del context["links"]
            contexts[url] = context

        for url in machine_urls:
            response = self.api_get_url(url)
            if response.status_code != 200:
                self.flash("Error getting machine.")
                return self.redirect("app.index")
            machine = response.json
            del machine["links"]
            machines[url] = machine

        graph = get_graph_definition(benchmark_name)
        group_by_key = graph.get("time_series_group_by", "")
        by_group = tree()
        context_urls, machine_urls = [], []
        for benchmark in benchmarks:
            context_url = benchmark["links"]["context"]
            machine_url = benchmark["links"]["machine"]
            tags = benchmark["tags"]
            augment(benchmark)
            benchmark["context"] = contexts.get(context_url, {})
            benchmark["machine_info"] = machines.get(machine_url, {})
            tags_hash = hashable(tags)
            group_by = tags.get(group_by_key, "")
            key = f"{machine_url}, {context_url}"
            by_group[group_by][tags_hash][key][benchmark["id"]] = benchmark

        return self.page(by_group, benchmark_name, graph)

    def _get_benchmarks(self, benchmark_name):
        response = self.api_get("api.benchmarks", name=benchmark_name)
        return response.json, response


class TimeSeriesList(AppEndpoint):
    def page(self, by_name):
        plots, names, i = [], [], 1
        for benchmark_name, benchmarks in by_name.items():
            by_group = collections.defaultdict(list)
            names.append(benchmark_name)
            graph = get_graph_definition(benchmark_name)
            group_by_key = graph.get("time_series_group_by", "")
            for benchmark in benchmarks:
                tags = benchmark["tags"]
                group_by = tags.get(group_by_key, "")
                by_group[group_by].append(benchmark)
            p = summary_scatter_plot(by_group, graph)
            if p:
                plot = json.dumps(bokeh.embed.json_item(p, f"plot{i}"))
                plots.append(plot)
                i += 1

        return self.render_template(
            "series-list.html",
            application=Config.APPLICATION_NAME,
            title="Time Series",
            resources=bokeh.resources.CDN.render(),
            plots=plots,
            names=names,
        )

    def get(self):
        benchmarks, response = self._get_benchmarks()
        if response.status_code != 200:
            self.flash("Error getting benchmarks.")
            return self.redirect("app.index")

        by_name = collections.defaultdict(list)
        for benchmark in benchmarks:
            augment(benchmark)
            name = benchmark["tags"]["name"].replace("/", "..")
            by_name[name].append(benchmark)

        return self.page(by_name)

    def _get_benchmarks(self):
        response = self.api_get("api.benchmarks")
        return response.json, response


rule(
    "/series/",
    view_func=TimeSeriesList.as_view("series"),
    methods=["GET"],
)
rule(
    "/series/<benchmark_name>/",
    view_func=TimeSeriesPlot.as_view("benchmark-series"),
    methods=["GET"],
)
