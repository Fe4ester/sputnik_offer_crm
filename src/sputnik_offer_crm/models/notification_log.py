"""NotificationLog model for deduplication."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from sputnik_offer_crm.db.base import Base
from sputnik_offer_crm.models.base import TimestampMixin


class NotificationLog(Base, TimestampMixin):
    """Log of sent notifications for deduplication."""

    __tablename__ = "notification_log"
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "notification_type",
            "notification_key",
            "sent_date",
            name="uq_notification_dedup",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    notification_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    notification_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    sent_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    message: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    def __repr__(self) -> str:
        return f"<NotificationLog(id={self.id}, student_id={self.student_id}, type={self.notification_type})>"
