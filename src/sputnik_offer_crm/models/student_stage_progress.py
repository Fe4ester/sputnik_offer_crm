"""Student stage progress model according to db-schema.txt."""

import enum
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, DateTime, Enum, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sputnik_offer_crm.db.base import Base

if TYPE_CHECKING:
    from sputnik_offer_crm.models.stage import Stage
    from sputnik_offer_crm.models.student import Student


class StageProgressStatus(str, enum.Enum):
    """Stage progress status (db-schema.txt values)."""

    NOT_STARTED = "not_started"
    ACTIVE = "active"
    DONE = "done"
    SKIPPED = "skipped"


class StudentStageProgress(Base):
    """Student progress on a specific stage (from db-schema.txt)."""

    __tablename__ = "student_stage_progress"

    __table_args__ = (
        UniqueConstraint("student_id", "stage_id", name="uq_student_stage"),
        CheckConstraint(
            "completed_at >= started_at",
            name="ck_student_stage_progress_dates",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    stage_id: Mapped[int] = mapped_column(
        ForeignKey("stages.id"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Enum(
            "not_started",
            "active",
            "done",
            "skipped",
            name="stage_progress_status",
            create_constraint=True,
        ),
        default="not_started",
        nullable=False,
    )
    started_at: Mapped[date | None] = mapped_column(Date)
    completed_at: Mapped[date | None] = mapped_column(Date)
    planned_deadline: Mapped[date | None] = mapped_column(Date)
    mentor_comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    student: Mapped["Student"] = relationship(back_populates="stage_progress")
    stage: Mapped["Stage"] = relationship()
