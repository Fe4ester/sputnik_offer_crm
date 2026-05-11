"""Direction and DirectionStage models."""

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from sputnik_offer_crm.db.base import Base
from sputnik_offer_crm.models.base import TimestampMixin


class Direction(Base, TimestampMixin):
    """Learning direction (e.g., Python, Frontend, etc.)."""

    __tablename__ = "directions"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<Direction(id={self.id}, code={self.code}, name={self.name})>"


class DirectionStage(Base, TimestampMixin):
    """Stage within a direction."""

    __tablename__ = "direction_stages"
    __table_args__ = (
        UniqueConstraint("direction_id", "id", name="uq_direction_stage_composite"),
        UniqueConstraint("direction_id", "order_index", name="uq_direction_stage_order"),
        CheckConstraint("order_index >= 0", name="ck_direction_stage_order_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    direction_id: Mapped[int] = mapped_column(
        ForeignKey("directions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    order_index: Mapped[int] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    is_final: Mapped[bool] = mapped_column(default=False, nullable=False)

    def __repr__(self) -> str:
        return f"<DirectionStage(id={self.id}, direction_id={self.direction_id}, order={self.order_index})>"
