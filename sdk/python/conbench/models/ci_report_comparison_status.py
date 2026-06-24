from enum import Enum


class CIReportComparisonStatus(str, Enum):
    ERRORED = "errored"
    IMPROVED = "improved"
    INSUFFICIENT = "insufficient"
    MISSING_BASELINE = "missing_baseline"
    NOT_COMPARABLE = "not_comparable"
    REGRESSED = "regressed"
    STABLE = "stable"

    def __str__(self) -> str:
        return str(self.value)
