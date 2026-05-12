"""Weekly report model."""

from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from sputnik_offer_crm.db.base import Base


class WeeklyReport(Base):
    """Student weekly report submission."""

    __tablename__ = "weekly_reports"

    __table_args__ = (
        UniqueConstraint("student_id", "week_start_date", name="uq_student_week"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    week_start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="Monday of the week in student's local timezone",
    )
    answer_what_did: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="What did you do last week? What did you learn?",
    )
    answer_problems_solved: Mapped[str | None] = mapped_column(
        Text,
        comment="What problems did you encounter and solve?",
    )
    answer_problems_unsolved: Mapped[str | None] = mapped_column(
        Text,
        comment="What problems do you need help with?",
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<WeeklyReport(id={self.id}, student_id={self.student_id}, week={self.week_start_date})>"
