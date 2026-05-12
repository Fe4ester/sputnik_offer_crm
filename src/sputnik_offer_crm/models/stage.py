"""Stage model according to db-schema.txt."""

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from sputnik_offer_crm.db.base import Base
from sputnik_offer_crm.models.base import TimestampMixin


class Stage(Base, TimestampMixin):
    """Stage within a direction (from db-schema.txt)."""

    __tablename__ = "stages"

    __table_args__ = (
        UniqueConstraint("direction_id", "stage_number", name="uq_direction_stage_number"),
        CheckConstraint("stage_number > 0", name="ck_stage_number_positive"),
        CheckConstraint(
            "planned_duration_days IS NULL OR planned_duration_days > 0",
            name="ck_planned_duration_positive",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    direction_id: Mapped[int] = mapped_column(
        ForeignKey("directions.id"),
        nullable=False,
        index=True,
    )
    stage_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    planned_duration_days: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<Stage(id={self.id}, direction_id={self.direction_id}, stage_number={self.stage_number})>"
