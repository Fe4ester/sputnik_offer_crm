"""Student model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sputnik_offer_crm.db.base import Base
from sputnik_offer_crm.models.base import TimestampMixin
from sputnik_offer_crm.models.student_status import StudentStatus

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

    # New unified status field (aligned with db-schema.txt)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=StudentStatus.ACTIVE.value,
        index=True,
    )

    # Legacy fields - kept for backward compatibility during transition
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
        return f"<Student(id={self.id}, telegram_id={self.telegram_id}, status={self.status})>"

    # Helper methods for status management
    def get_status(self) -> StudentStatus:
        """Get student status as enum."""
        return StudentStatus(self.status)

    def set_status(self, new_status: StudentStatus) -> None:
        """
        Set student status and sync legacy fields.

        This ensures backward compatibility with existing code
        that reads is_active/is_paused.
        """
        self.status = new_status.value

        # Sync legacy fields for backward compatibility
        if new_status == StudentStatus.DROPPED:
            self.is_active = False
            self.is_paused = False
        elif new_status == StudentStatus.PAUSED:
            self.is_active = True
            self.is_paused = True
        else:  # ACTIVE
            self.is_active = True
            self.is_paused = False

    def is_eligible_for_notifications(self) -> bool:
        """Check if student should receive notifications."""
        return self.status == StudentStatus.ACTIVE.value

    def is_on_pause(self) -> bool:
        """Check if student is paused."""
        return self.status == StudentStatus.PAUSED.value

    def is_dropped(self) -> bool:
        """Check if student is dropped."""
        return self.status == StudentStatus.DROPPED.value
