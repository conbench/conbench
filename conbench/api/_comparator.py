import decimal

from ..units import formatter_for_unit


THRESHOLD = 5  # percent


def fmt(value):
    return "{:.3f}".format(value) if value is not None else None


def change_fmt(value):
    return "{:.3%}".format(value)


class BenchmarkResult:
    def __init__(self, id, batch_id, run_id, unit, value, batch, benchmark, tags):
        self.id = id
        self.batch_id = batch_id
        self.run_id = run_id
        self.unit = unit
        self.batch = batch
        self.benchmark = benchmark
        self.value = decimal.Decimal(value)
        self.tags = tags


class BenchmarkComparator:
    def __init__(self, baseline, contender, threshold=None):
        self.baseline = BenchmarkResult(**baseline) if baseline else None
        self.contender = BenchmarkResult(**contender) if contender else None
        self.threshold = threshold if threshold is not None else THRESHOLD

    @property
    def batch(self):
        if self.baseline is not None:
            return self.baseline.batch
        if self.contender is not None:
            return self.contender.batch
        return "unknown"

    @property
    def benchmark(self):
        if self.baseline is not None:
            return self.baseline.benchmark
        if self.contender is not None:
            return self.contender.benchmark
        return "unknown"

    @property
    def unit(self):
        if self.baseline is not None:
            return self.baseline.unit
        if self.contender is not None:
            return self.contender.unit
        return "unknown"

    @property
    def less_is_better(self):
        if self.unit in ["B/s", "i/s"]:
            return False
        return True

    @property
    def change(self):
        if self.baseline is None or self.contender is None:
            return 0.0

        new = self.contender.value
        old = self.baseline.value

        if old == 0 and new == 0:
            return 0.0
        if old == 0:
            return 0.0

        return (new - old) / abs(old)

    @property
    def regression(self):
        change = self.change
        adjusted_change = change if self.less_is_better else -change
        return adjusted_change * 100 > self.threshold

    @property
    def improvement(self):
        change = self.change
        adjusted_change = -change if self.less_is_better else change
        return adjusted_change * 100 > self.threshold

    @property
    def z_score(self):
        return 0.0  # TODO

    @property
    def regression_z(self):
        return False  # TODO

    @property
    def improvement_z(self):
        return False  # TODO

    @property
    def tags(self):
        if self.baseline is not None:
            return self.baseline.tags
        if self.contender is not None:
            return self.contender.tags
        return "unknown"

    def formatted(self):
        fmt_unit = formatter_for_unit(self.unit)
        baseline = self.baseline.value if self.baseline else None
        contender = self.contender.value if self.contender else None
        return {
            "batch": self.batch,
            "benchmark": self.benchmark,
            "change": change_fmt(self.change),
            "threshold": self.threshold,  # TODO: change_fmt?
            "regression": self.regression,
            "improvement": self.improvement,
            "z_score": fmt(self.z_score),
            "regression_z": self.regression_z,
            "improvement_z": self.improvement_z,
            "baseline": fmt_unit(baseline, self.unit),
            "contender": fmt_unit(contender, self.unit),
            "baseline_id": self.baseline.id if self.baseline else None,
            "contender_id": self.contender.id if self.contender else None,
            "baseline_batch_id": self.baseline.batch_id if self.baseline else None,
            "contender_batch_id": self.contender.batch_id if self.contender else None,
            "baseline_run_id": self.baseline.run_id if self.baseline else None,
            "contender_run_id": self.contender.run_id if self.contender else None,
            "unit": self.unit,
            "less_is_better": self.less_is_better,
            "tags": self.tags,
        }

    def compare(self):
        baseline = self.baseline.value if self.baseline else None
        contender = self.contender.value if self.contender else None
        return {
            "batch": self.batch,
            "benchmark": self.benchmark,
            "change": fmt(self.change * 100),
            "threshold": self.threshold,
            "regression": self.regression,
            "improvement": self.improvement,
            "z_score": fmt(self.z_score),
            "regression_z": self.regression_z,
            "improvement_z": self.improvement_z,
            "baseline": fmt(baseline),
            "contender": fmt(contender),
            "baseline_id": self.baseline.id if self.baseline else None,
            "contender_id": self.contender.id if self.contender else None,
            "baseline_batch_id": self.baseline.batch_id if self.baseline else None,
            "contender_batch_id": self.contender.batch_id if self.contender else None,
            "baseline_run_id": self.baseline.run_id if self.baseline else None,
            "contender_run_id": self.contender.run_id if self.contender else None,
            "unit": self.unit,
            "less_is_better": self.less_is_better,
            "tags": self.tags,
        }


class BenchmarkListComparator:
    def __init__(self, pairs, threshold=None):
        self.pairs = pairs
        self.threshold = threshold if threshold is not None else THRESHOLD

    def formatted(self):
        for pair in self.pairs.values():
            baseline, contender = pair.get("baseline"), pair.get("contender")
            yield BenchmarkComparator(baseline, contender, self.threshold).formatted()

    def compare(self):
        for pair in self.pairs.values():
            baseline, contender = pair.get("baseline"), pair.get("contender")
            yield BenchmarkComparator(baseline, contender, self.threshold).compare()
