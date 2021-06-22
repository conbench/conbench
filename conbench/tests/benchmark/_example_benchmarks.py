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
        return self.conbench.run(
            self._get_benchmark_function(), self.name, options=kwargs
        )

    def _get_benchmark_function(self):
        return lambda: 1 + 1


@conbench.runner.register_benchmark
class ExternalBenchmark(conbench.runner.Benchmark):
    """Example benchmark that just records external results."""

    external = True
    name = "external"

    def run(self, **kwargs):
        # external results from an API call, command line execution, etc
        data = {
            "data": [100, 200, 300],
            "unit": "i/s",
            "times": [0.100, 0.200, 0.300],
            "time_unit": "s",
        }

        context = {"benchmark_language": "C++"}
        return self.conbench.external(
            data, self.name, context=context, options=kwargs, output=data
        )


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
            self.conbench.publish(benchmark)
            yield benchmark, output

    def _get_benchmark_function(self, rows, columns):
        return lambda: int(rows) * [int(columns) * [0]]
