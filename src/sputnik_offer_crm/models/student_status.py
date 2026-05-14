"""Student status enum."""

from enum import Enum


class StudentStatus(str, Enum):
    """Student lifecycle status."""

    ACTIVE = "active"
    PAUSED = "paused"
    DROPPED = "dropped"

    def __str__(self) -> str:
        return self.value
