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

    def __init__(self):
        self.conbench = conbench.runner.Conbench()

    def run(self, **kwargs):
        def func():
            return 1 + 1

        tags, context = {"year": "2020"}, {}
        github_info = {
            "commit": "02addad336ba19a654f9c857ede546331be7b631",
            "repository": "https://github.com/apache/arrow",
        }
        benchmark, output = self.conbench.benchmark(
            func,
            self.name,
            tags,
            context,
            github_info,
            kwargs,
        )
        self.conbench.publish(benchmark)
        yield benchmark, output


@conbench.runner.register_benchmark
class ExternalBenchmark(conbench.runner.Benchmark):
    """Example benchmark that just records external results."""

    external = True
    name = "external"

    def __init__(self):
        self.conbench = conbench.runner.Conbench()

    def run(self, **kwargs):
        tags, context = {"year": "2020"}, {"benchmark_language": "C++"}
        github_info = {
            "commit": "02addad336ba19a654f9c857ede546331be7b631",
            "repository": "https://github.com/apache/arrow",
        }

        # external results from somewhere
        # (an API call, command line execution, etc)
        result = {
            "data": [100, 200, 300],
            "unit": "i/s",
            "times": [0.100, 0.200, 0.300],
            "time_unit": "s",
        }

        benchmark, output = self.conbench.record(
            result,
            self.name,
            tags,
            context,
            github_info,
            kwargs,
            output=result["data"],
        )
        self.conbench.publish(benchmark)
        yield benchmark, output


@conbench.runner.register_benchmark
class CasesBenchmark(conbench.runner.Benchmark):
    """Example benchmark with cases, an option, and an argument."""

    name = "subtraction"
    valid_cases = (
        ("color", "fruit"),
        ("pink", "apple"),
        ("yellow", "apple"),
        ("green", "apple"),
        ("yellow", "orange"),
        ("pink", "orange"),
    )
    arguments = ["source"]
    options = {"count": {"default": 1, "type": int}}

    def __init__(self):
        self.conbench = conbench.runner.Conbench()

    def run(self, source, case=None, count=1, **kwargs):
        def func():
            return 100 - 1

        context = {}
        github_info = {
            "commit": "02addad336ba19a654f9c857ede546331be7b631",
            "repository": "https://github.com/apache/arrow",
        }
        for case in self.get_cases(case, kwargs):
            color, fruit = case
            tags = {
                "color": color,
                "fruit": fruit,
                "count": count,
                "dataset": source,
            }
            benchmark, output = self.conbench.benchmark(
                func,
                self.name,
                tags,
                context,
                github_info,
                kwargs,
            )
            self.conbench.publish(benchmark)
            yield benchmark, output
