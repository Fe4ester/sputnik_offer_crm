"""Mentor model."""

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from sputnik_offer_crm.db.base import Base
from sputnik_offer_crm.models.base import TimestampMixin


class Mentor(Base, TimestampMixin):
    """Mentor who can create invite codes and manage students."""

    __tablename__ = "mentors"

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
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<Mentor(id={self.id}, telegram_id={self.telegram_id})>"
