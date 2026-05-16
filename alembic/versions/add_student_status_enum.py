"""Add student status enum

Revision ID: add_student_status_enum
Revises: 4413e3441ce0
Create Date: 2026-05-14 12:58:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_student_status_enum'
down_revision = '4413e3441ce0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add status column with default 'active'
    op.add_column(
        'students',
        sa.Column('status', sa.String(20), nullable=False, server_default='active')
    )

    # Migrate existing data based on is_active and is_paused
    # Logic:
    # - is_active=False -> 'dropped'
    # - is_active=True, is_paused=True -> 'paused'
    # - is_active=True, is_paused=False -> 'active'
    op.execute("""
        UPDATE students
        SET status = CASE
            WHEN is_active = FALSE THEN 'dropped'
            WHEN is_active = TRUE AND is_paused = TRUE THEN 'paused'
            ELSE 'active'
        END
    """)

    # Add index on status
    op.create_index('ix_students_status', 'students', ['status'])


def downgrade() -> None:
    op.drop_index('ix_students_status', table_name='students')
    op.drop_column('students', 'status')
