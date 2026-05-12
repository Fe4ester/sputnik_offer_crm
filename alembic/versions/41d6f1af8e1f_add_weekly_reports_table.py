"""add_weekly_reports_table

Revision ID: 41d6f1af8e1f
Revises: b8bbe441b1c4
Create Date: 2026-05-12 18:29:51.661624

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '41d6f1af8e1f'
down_revision: Union[str, None] = 'b8bbe441b1c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'weekly_reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('week_start_date', sa.Date(), nullable=False, comment='Monday of the week in student\'s local timezone'),
        sa.Column('answer_what_did', sa.Text(), nullable=False, comment='What did you do last week? What did you learn?'),
        sa.Column('answer_problems_solved', sa.Text(), nullable=True, comment='What problems did you encounter and solve?'),
        sa.Column('answer_problems_unsolved', sa.Text(), nullable=True, comment='What problems do you need help with?'),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('student_id', 'week_start_date', name='uq_student_week')
    )
    op.create_index(op.f('ix_weekly_reports_student_id'), 'weekly_reports', ['student_id'], unique=False)
    op.create_index(op.f('ix_weekly_reports_week_start_date'), 'weekly_reports', ['week_start_date'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_weekly_reports_week_start_date'), table_name='weekly_reports')
    op.drop_index(op.f('ix_weekly_reports_student_id'), table_name='weekly_reports')
    op.drop_table('weekly_reports')
