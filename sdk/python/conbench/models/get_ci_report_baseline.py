from enum import Enum


class GetCiReportBaseline(str, Enum):
    FORK_POINT = "fork_point"
    LATEST_DEFAULT = "latest_default"
    PARENT = "parent"

    def __str__(self) -> str:
        return str(self.value)
