"""add is_admin to mentors

Revision ID: c9f1b4a7d2f0
Revises: 049f51ffe618
Create Date: 2026-05-16 15:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c9f1b4a7d2f0"
down_revision: Union[str, None] = "049f51ffe618"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "mentors",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("mentors", "is_admin", server_default=None)


def downgrade() -> None:
    op.drop_column("mentors", "is_admin")
