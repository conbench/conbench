import decimal
from typing import Optional

import sigfig

from ..entities._entity import to_float

CHANGE = 5.0  # percent changed threshold
Z_SCORE = 5.0  # z-score threshold


def _round(value: Optional[float]) -> Optional[float]:
    return sigfig.round(value, sigfigs=4, warn=False) if value is not None else None


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
        error,
        benchmark_name,
        case_permutation,
        language,
        tags,
        z_score,
        **kwargs,
    ):
        self.id = id
        self.batch_id = batch_id
        self.run_id = run_id
        self.unit = unit
        self.benchmark_name = benchmark_name
        self.case_permutation = case_permutation
        self.value = decimal.Decimal(value) if value else None
        self.error = error
        self.tags = tags
        self.language = language
        self.z_score = float(z_score) if z_score is not None else None


class BenchmarkResultComparator:
    def __init__(self, baseline, contender, threshold=None, threshold_z=None):
        self.baseline = BenchmarkResult(**baseline) if baseline else None
        self.contender = BenchmarkResult(**contender) if contender else None
        self.threshold = float(threshold) if threshold is not None else CHANGE
        self.threshold_z = float(threshold_z) if threshold_z is not None else Z_SCORE

    @property
    def benchmark_name(self):
        if self.baseline is not None:
            return self.baseline.benchmark_name
        if self.contender is not None:
            return self.contender.benchmark_name
        return "unknown"

    @property
    def case_permutation(self):
        if self.baseline is not None:
            return self.baseline.case_permutation
        if self.contender is not None:
            return self.contender.case_permutation
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
        if self.baseline is not None and self.baseline.unit:
            return self.baseline.unit
        if self.contender is not None and self.contender.unit:
            return self.contender.unit
        return "unknown"

    @property
    def less_is_better(self):
        return _less_is_better(self.unit)

    @property
    def change(self):
        if self.baseline is None or self.contender is None:
            return 0.0

        if self.baseline.error or self.contender.error:
            return 0.0

        new = self.contender.value
        old = self.baseline.value

        if old == 0 and new == 0:
            return 0.0
        if old == 0:
            return 0.0
        if old is None or new is None:
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

    def compare(self):
        baseline = self.baseline.value if self.baseline else None
        contender = self.contender.value if self.contender else None
        return {
            "unit": self.unit,
            "less_is_better": self.less_is_better,
            "baseline": {
                "benchmark_name": self.baseline.benchmark_name,
                "case_permutation": self.baseline.case_permutation,
                "language": self.baseline.language,
                "value": _round(to_float(baseline)),
                "error": self.baseline.error,
                "benchmark_result_id": self.baseline.id,
                "batch_id": self.baseline.batch_id,
                "run_id": self.baseline.run_id,
                "tags": self.baseline.tags,
            }
            if self.baseline
            else None,
            "contender": {
                "benchmark_name": self.contender.benchmark_name,
                "case_permutation": self.contender.case_permutation,
                "language": self.contender.language,
                "value": _round(to_float(contender)),
                "error": self.contender.error,
                "benchmark_result_id": self.contender.id,
                "batch_id": self.contender.batch_id,
                "run_id": self.contender.run_id,
                "tags": self.contender.tags,
            }
            if self.contender
            else None,
            "analysis": {
                "pairwise": {
                    "percent_change": _round(to_float(self.change * 100)),
                    "percent_threshold": to_float(self.threshold),
                    "regression_indicated": self.regression,
                    "improvement_indicated": self.improvement,
                },
                "lookback_z_score": {
                    "z_threshold": to_float(self.threshold_z),
                    "z_score": _round(to_float(self.contender.z_score))
                    if self.contender
                    else None,
                    "regression_indicated": self.contender_z_regression,
                    "improvement_indicated": self.contender_z_improvement,
                },
            },
        }


class BenchmarkResultListComparator:
    def __init__(self, pairs, threshold=None, threshold_z=None):
        self.pairs = pairs
        self.threshold = float(threshold) if threshold is not None else CHANGE
        self.threshold_z = float(threshold_z) if threshold_z is not None else Z_SCORE

    def compare(self):
        for pair in self.pairs.values():
            baseline, contender = pair.get("baseline"), pair.get("contender")
            yield BenchmarkResultComparator(
                baseline,
                contender,
                self.threshold,
                self.threshold_z,
            ).compare()
