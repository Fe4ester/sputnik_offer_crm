"""StudentProgress model."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from sputnik_offer_crm.db.base import Base
from sputnik_offer_crm.models.base import TimestampMixin


class StudentProgress(Base, TimestampMixin):
    """Student's progress in a direction."""

    __tablename__ = "student_progress"
    __table_args__ = (
        UniqueConstraint("student_id", "direction_id", name="uq_student_direction"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    direction_id: Mapped[int] = mapped_column(
        ForeignKey("directions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    current_stage_id: Mapped[int] = mapped_column(
        ForeignKey("stages.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<StudentProgress(id={self.id}, student_id={self.student_id}, direction_id={self.direction_id})>"
