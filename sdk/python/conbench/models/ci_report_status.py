from enum import Enum


class CIReportStatus(str, Enum):
    ACTION_REQUIRED = "action_required"
    FAILURE = "failure"
    SKIPPED = "skipped"
    SUCCESS = "success"

    def __str__(self) -> str:
        return str(self.value)
