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
class WithoutCasesBenchmark(conbench.runner.Benchmark):
    name = "addition"

    def __init__(self):
        self.conbench = conbench.runner.Conbench()

    def run(self, **kwargs):
        def func():
            return 1 + 1

        github_info = {}
        benchmark, output = self.conbench.benchmark(
            func,
            self.name,
            {"year": "2020"},
            {"benchmark_language": "Python"},
            github_info,
            {"iterations": 10},
        )
        self.conbench.publish(benchmark)
        yield benchmark, output


@conbench.runner.register_benchmark
class WithCasesBenchmark(conbench.runner.Benchmark):
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

        cases, github_info = self.get_cases(case, kwargs), {}
        for case in cases:
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
                {"benchmark_language": "Python"},
                github_info,
                {"iterations": 10},
            )
            self.conbench.publish(benchmark)
            yield benchmark, output
