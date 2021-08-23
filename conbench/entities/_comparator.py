import decimal

from ..units import formatter_for_unit

CHANGE = 5.0  # percent changed threshold
Z_SCORE = 5.0  # z-score threshold


def fmt(value):
    return "{:.3f}".format(value) if value is not None else None


def change_fmt(value):
    return "{:.3%}".format(value)


def _less_is_better(unit):
    if unit in ["B/s", "i/s"]:
        return False
    return True


def z_regression(z_score, threshold_z=None):
    if z_score is None:
        return False
    threshold_z = threshold_z if threshold_z else Z_SCORE
    return -z_score > threshold_z


def z_improvement(z_score, threshold_z=None):
    if z_score is None:
        return False
    threshold_z = threshold_z if threshold_z else Z_SCORE
    return z_score > threshold_z


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
        language,
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
        self.language = language
        self.z_score = decimal.Decimal(z_score) if z_score is not None else None


class BenchmarkComparator:
    def __init__(self, baseline, contender, threshold=None, threshold_z=None):
        self.baseline = BenchmarkResult(**baseline) if baseline else None
        self.contender = BenchmarkResult(**contender) if contender else None
        self.threshold = float(threshold) if threshold is not None else CHANGE
        self.threshold_z = float(threshold_z) if threshold_z is not None else Z_SCORE

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
    def language(self):
        if self.baseline is not None:
            return self.baseline.language
        if self.contender is not None:
            return self.contender.language
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
        return _less_is_better(self.unit)

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

        result = (new - old) / abs(old)
        if self.less_is_better and result != 0:
            result = result * -1

        return result

    @property
    def regression(self):
        return -self.change * 100 > self.threshold

    @property
    def improvement(self):
        return self.change * 100 > self.threshold

    @property
    def baseline_z_score(self):
        if self.baseline is None:
            return None
        return self.baseline.z_score

    @property
    def contender_z_score(self):
        if self.contender is None:
            return None
        return self.contender.z_score

    @property
    def baseline_z_regression(self):
        return z_regression(self.baseline_z_score, self.threshold_z)

    @property
    def baseline_z_improvement(self):
        return z_improvement(self.baseline_z_score, self.threshold_z)

    @property
    def contender_z_regression(self):
        return z_regression(self.contender_z_score, self.threshold_z)

    @property
    def contender_z_improvement(self):
        return z_improvement(self.contender_z_score, self.threshold_z)

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
            "language": self.language,
            "change": change_fmt(self.change),
            "threshold": fmt(self.threshold) + "%",
            "regression": self.regression,
            "improvement": self.improvement,
            "threshold_z": fmt(self.threshold_z),
            "baseline_z_score": fmt(self.baseline_z_score),
            "contender_z_score": fmt(self.contender_z_score),
            "baseline_z_regression": self.baseline_z_regression,
            "baseline_z_improvement": self.baseline_z_improvement,
            "contender_z_regression": self.contender_z_regression,
            "contender_z_improvement": self.contender_z_improvement,
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
            "language": self.language,
            "change": fmt(self.change * 100),
            "threshold": fmt(self.threshold),
            "regression": self.regression,
            "improvement": self.improvement,
            "threshold_z": fmt(self.threshold_z),
            "baseline_z_score": fmt(self.baseline_z_score),
            "contender_z_score": fmt(self.contender_z_score),
            "baseline_z_regression": self.baseline_z_regression,
            "baseline_z_improvement": self.baseline_z_improvement,
            "contender_z_regression": self.contender_z_regression,
            "contender_z_improvement": self.contender_z_improvement,
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
    def __init__(self, pairs, threshold=None, threshold_z=None):
        self.pairs = pairs
        self.threshold = float(threshold) if threshold is not None else CHANGE
        self.threshold_z = float(threshold_z) if threshold_z is not None else Z_SCORE

    def formatted(self):
        for pair in self.pairs.values():
            baseline, contender = pair.get("baseline"), pair.get("contender")
            yield BenchmarkComparator(
                baseline,
                contender,
                self.threshold,
                self.threshold_z,
            ).formatted()

    def compare(self):
        for pair in self.pairs.values():
            baseline, contender = pair.get("baseline"), pair.get("contender")
            yield BenchmarkComparator(
                baseline,
                contender,
                self.threshold,
                self.threshold_z,
            ).compare()
