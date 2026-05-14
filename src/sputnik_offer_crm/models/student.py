"""Student model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sputnik_offer_crm.db.base import Base
from sputnik_offer_crm.models.base import TimestampMixin

if TYPE_CHECKING:
    from sputnik_offer_crm.models.student_stage_progress import StudentStageProgress
    from sputnik_offer_crm.models.student_task import StudentTask


class Student(Base, TimestampMixin):
    """Student registered via invite code."""

    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        index=True,
    )
    first_name: Mapped[str] = mapped_column(String(255), nullable=False)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    is_paused: Mapped[bool] = mapped_column(default=False, nullable=False)

    offer_company: Mapped[str | None] = mapped_column(Text, nullable=True)
    offer_position: Mapped[str | None] = mapped_column(Text, nullable=True)
    offer_received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    stage_progress: Mapped[list["StudentStageProgress"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )
    tasks: Mapped[list["StudentTask"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Student(id={self.id}, telegram_id={self.telegram_id}, timezone={self.timezone})>"
