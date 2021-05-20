import decimal

from ..units import formatter_for_unit


THRESHOLD = 5.0  # percent
DEVIATIONS = 2.0  # standard deviations


def fmt(value):
    return "{:.3f}".format(value) if value is not None else None


def change_fmt(value):
    return "{:.3%}".format(value)


class BenchmarkResult:
    def __init__(
        self,
        id,
        batch_id,
        run_id,
        unit,
        value,
        batch,
        benchmark,
        tags,
        z_score,
    ):
        self.id = id
        self.batch_id = batch_id
        self.run_id = run_id
        self.unit = unit
        self.batch = batch
        self.benchmark = benchmark
        self.value = decimal.Decimal(value)
        self.tags = tags
        self.z_score = decimal.Decimal(z_score)


class BenchmarkComparator:
    def __init__(self, baseline, contender, threshold=None, deviations=None):
        self.baseline = BenchmarkResult(**baseline) if baseline else None
        self.contender = BenchmarkResult(**contender) if contender else None
        self.threshold = float(threshold) if threshold is not None else THRESHOLD
        self.deviations = float(deviations) if deviations is not None else DEVIATIONS

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
    def baseline_z_score(self):
        if self.baseline is None:
            return 0.0
        return self.baseline.z_score

    @property
    def contender_z_score(self):
        if self.contender is None:
            return 0.0
        return self.contender.z_score

    @property
    def baseline_regression_z(self):
        z_score = self.baseline_z_score
        adjusted_z_score = z_score if self.less_is_better else -z_score
        return adjusted_z_score > self.deviations

    @property
    def baseline_improvement_z(self):
        z_score = self.baseline_z_score
        adjusted_z_score = -z_score if self.less_is_better else z_score
        return adjusted_z_score > self.deviations

    @property
    def contender_regression_z(self):
        z_score = self.contender_z_score
        adjusted_z_score = z_score if self.less_is_better else -z_score
        return adjusted_z_score > self.deviations

    @property
    def contender_improvement_z(self):
        z_score = self.contender_z_score
        adjusted_z_score = -z_score if self.less_is_better else z_score
        return adjusted_z_score > self.deviations

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
            "threshold": fmt(self.threshold) + "%",
            "regression": self.regression,
            "improvement": self.improvement,
            "baseline_z_score": fmt(self.baseline_z_score),
            "contender_z_score": fmt(self.contender_z_score),
            "baseline_regression_z": self.baseline_regression_z,
            "baseline_improvement_z": self.baseline_improvement_z,
            "contender_regression_z": self.contender_regression_z,
            "contender_improvement_z": self.contender_improvement_z,
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
            "threshold": fmt(self.threshold),
            "regression": self.regression,
            "improvement": self.improvement,
            "baseline_z_score": fmt(self.baseline_z_score),
            "contender_z_score": fmt(self.contender_z_score),
            "baseline_regression_z": self.baseline_regression_z,
            "baseline_improvement_z": self.baseline_improvement_z,
            "contender_regression_z": self.contender_regression_z,
            "contender_improvement_z": self.contender_improvement_z,
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
    def __init__(self, pairs, threshold=None, deviations=None):
        self.pairs = pairs
        self.threshold = float(threshold) if threshold is not None else THRESHOLD
        self.deviations = float(deviations) if deviations is not None else DEVIATIONS

    def formatted(self):
        for pair in self.pairs.values():
            baseline, contender = pair.get("baseline"), pair.get("contender")
            yield BenchmarkComparator(
                baseline,
                contender,
                self.threshold,
                self.deviations,
            ).formatted()

    def compare(self):
        for pair in self.pairs.values():
            baseline, contender = pair.get("baseline"), pair.get("contender")
            yield BenchmarkComparator(
                baseline,
                contender,
                self.threshold,
                self.deviations,
            ).compare()
