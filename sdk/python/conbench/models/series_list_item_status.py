from enum import Enum


class SeriesListItemStatus(str, Enum):
    IMPROVED = "improved"
    INSUFFICIENT = "insufficient"
    REGRESSED = "regressed"
    STABLE = "stable"

    def __str__(self) -> str:
        return str(self.value)
