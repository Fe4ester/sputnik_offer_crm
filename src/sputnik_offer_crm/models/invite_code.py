"""InviteCode model."""

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from sputnik_offer_crm.db.base import Base


class InviteCode(Base):
    """One-time invite code for student registration."""

    __tablename__ = "invite_codes"
    __table_args__ = (
        CheckConstraint("length(code) >= 6 AND length(code) <= 20", name="ck_invite_code_length"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
    )
    mentor_id: Mapped[int] = mapped_column(
        ForeignKey("mentors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    direction_id: Mapped[int] = mapped_column(
        ForeignKey("directions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    suggested_timezone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    used_by_student_id: Mapped[int | None] = mapped_column(
        ForeignKey("students.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<InviteCode(id={self.id}, code={self.code}, used={self.used_at is not None})>"
