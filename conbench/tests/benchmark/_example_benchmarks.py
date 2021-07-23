import json

import conbench.runner


@conbench.runner.register_list
class BenchmarkList(conbench.runner.BenchmarkList):
    def list(self, classes):
        benchmarks = []
        for name, benchmark in classes.items():
            instance, parts = benchmark(), [name]
            if instance.cases:
                parts.append("--all=true")
            parts.append("--iterations=2")
            benchmarks.append({"command": " ".join(parts)})
        return sorted(benchmarks, key=lambda k: k["command"])


@conbench.runner.register_benchmark
class SimpleBenchmark(conbench.runner.Benchmark):
    """Example benchmark without cases."""

    name = "addition"

    def run(self, **kwargs):
        yield self.conbench.benchmark(
            self._get_benchmark_function(), self.name, options=kwargs
        )

    def _get_benchmark_function(self):
        return lambda: 1 + 1


@conbench.runner.register_benchmark
class CasesBenchmark(conbench.runner.Benchmark):
    """Example benchmark with cases."""

    name = "matrix"
    valid_cases = (
        ("rows", "columns"),
        ("10", "10"),
        ("2", "10"),
        ("10", "2"),
    )

    def run(self, case=None, **kwargs):
        for case in self.get_cases(case, kwargs):
            rows, columns = case
            tags = {"rows": rows, "columns": columns}
            func = self._get_benchmark_function(rows, columns)
            benchmark, output = self.conbench.benchmark(
                func,
                self.name,
                tags=tags,
                options=kwargs,
            )
            yield benchmark, output

    def _get_benchmark_function(self, rows, columns):
        return lambda: int(rows) * [int(columns) * [0]]


@conbench.runner.register_benchmark
class ExternalBenchmark(conbench.runner.Benchmark):
    """Example benchmark that just records external results."""

    external = True
    name = "external"

    def run(self, **kwargs):
        # external results from an API call, command line execution, etc
        result = {
            "data": [100, 200, 300],
            "unit": "i/s",
            "times": [0.100, 0.200, 0.300],
            "time_unit": "s",
        }

        context = {"benchmark_language": "C++"}
        yield self.conbench.record(
            result, self.name, context=context, options=kwargs, output=result
        )


@conbench.runner.register_benchmark
class ExternalBenchmarkR(conbench.runner.Benchmark):
    """Example benchmark that records an R benchmark result."""

    external = True
    name = "external-r"

    def run(self, **kwargs):
        result, output = self._run_r_command()
        yield self.conbench.record(
            {"data": [result], "unit": "s"},
            self.name,
            context=self.conbench.r_info,
            options=kwargs,
            output=output,
        )

    def _run_r_command(self):
        output, _ = self.conbench.execute_r_command(self._get_r_command())
        result = float(output.split("\n")[-1].split("[1] ")[1])
        return result, output

    def _get_r_command(self):
        return (
            f"addition <- function() { 1 + 1 }; "
            "start_time <- Sys.time();"
            "addition(); "
            "end_time <- Sys.time(); "
            "result <- end_time - start_time; "
            "as.numeric(result); "
        )


@conbench.runner.register_benchmark
class ExternalBenchmarkOptionsR(conbench.runner.Benchmark):
    """Example benchmark that records an R benchmark result (with options)."""

    external = True
    name = "external-r-options"
    options = {
        "iterations": {"default": 1, "type": int},
        "drop_caches": {"type": bool, "default": "false"},
    }

    def run(self, **kwargs):
        data, iterations = [], kwargs.get("iterations", 1)

        for _ in range(iterations):
            if kwargs.get("drop_caches", False):
                self.conbench.sync_and_drop_caches()
            result, output = self._run_r_command()
            data.append(result["result"][0]["real"])

        yield self.conbench.record(
            {"data": data, "unit": "s"},
            self.name,
            context=self.conbench.r_info,
            options=kwargs,
            output=output,
        )

    def _run_r_command(self):
        r_command = self._get_r_command()
        self.conbench.execute_r_command(r_command)
        with open("placebo.json") as json_file:
            data = json.load(json_file)
        return data, json.dumps(data, indent=2)

    def _get_r_command(self):
        return (
            "library(arrowbench); "
            "out <- run_one(arrowbench:::placebo); "
            "cat(jsonlite::toJSON(out), file='placebo.json'); "
        )
