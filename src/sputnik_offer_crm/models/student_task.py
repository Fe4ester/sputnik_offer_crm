"""Student task model according to db-schema.txt."""

import enum
from datetime import date, datetime, timezone

from sqlalchemy import CheckConstraint, Date, DateTime, Enum, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sputnik_offer_crm.db.base import Base


class TaskStatus(str, enum.Enum):
    """Task status (db-schema.txt values)."""

    OPEN = "open"
    DONE = "done"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class StudentTask(Base):
    """Student task (from db-schema.txt)."""

    __tablename__ = "student_tasks"

    __table_args__ = (
        CheckConstraint("task_order IS NULL OR task_order > 0", name="ck_task_order_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    task_order: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    deadline: Mapped[date | None] = mapped_column(Date)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mentor_task: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        Enum(
            "open",
            "done",
            "overdue",
            "cancelled",
            name="task_status",
            create_constraint=True,
        ),
        default="open",
        nullable=False,
    )
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
    student: Mapped["Student"] = relationship(back_populates="tasks")
