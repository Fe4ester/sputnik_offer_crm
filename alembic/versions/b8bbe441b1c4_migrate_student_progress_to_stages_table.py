"""migrate_student_progress_to_stages_table

Revision ID: b8bbe441b1c4
Revises: 61c117a4ebf4
Create Date: 2026-05-12 18:18:10.136285

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8bbe441b1c4'
down_revision: Union[str, None] = '61c117a4ebf4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    # Step 1: Copy data from direction_stages to stages
    # Map order_index to stage_number (order_index is 0-based, stage_number is 1-based)
    if dialect_name == "sqlite":
        op.execute("""
            INSERT OR IGNORE INTO stages (
                direction_id,
                stage_number,
                title,
                description,
                planned_duration_days,
                is_active,
                created_at,
                updated_at
            )
            SELECT
                direction_id,
                order_index + 1 as stage_number,
                name as title,
                NULL as description,
                NULL as planned_duration_days,
                is_active,
                created_at,
                updated_at
            FROM direction_stages
        """)
    else:
        op.execute("""
            INSERT INTO stages (
                direction_id,
                stage_number,
                title,
                description,
                planned_duration_days,
                is_active,
                created_at,
                updated_at
            )
            SELECT
                direction_id,
                order_index + 1 as stage_number,
                name as title,
                NULL as description,
                NULL as planned_duration_days,
                is_active,
                created_at,
                updated_at
            FROM direction_stages
            ON CONFLICT DO NOTHING
        """)

    # Step 2: Create a mapping table to update student_progress
    # We need to map old direction_stage.id to new stage.id
    op.execute("""
        CREATE TEMP TABLE stage_id_mapping AS
        SELECT
            ds.id as old_stage_id,
            s.id as new_stage_id
        FROM direction_stages ds
        JOIN stages s ON s.direction_id = ds.direction_id AND s.stage_number = ds.order_index + 1
    """)

    # Step 3: Drop the old composite foreign key constraint
    if dialect_name == "sqlite":
        with op.batch_alter_table("student_progress", recreate="always") as batch_op:
            batch_op.drop_constraint(
                "fk_student_progress_direction_stage",
                type_="foreignkey",
            )
            batch_op.create_foreign_key(
                "fk_student_progress_stage",
                "stages",
                ["current_stage_id"],
                ["id"],
                ondelete="RESTRICT",
            )
    else:
        op.drop_constraint(
            'fk_student_progress_direction_stage',
            'student_progress',
            type_='foreignkey',
        )

    # Step 4: Update student_progress.current_stage_id to point to stages table
    if dialect_name == "sqlite":
        op.execute("""
            UPDATE student_progress
            SET current_stage_id = (
                SELECT m.new_stage_id
                FROM stage_id_mapping m
                WHERE m.old_stage_id = student_progress.current_stage_id
            )
            WHERE current_stage_id IN (
                SELECT old_stage_id FROM stage_id_mapping
            )
        """)
    else:
        op.execute("""
            UPDATE student_progress sp
            SET current_stage_id = m.new_stage_id
            FROM stage_id_mapping m
            WHERE sp.current_stage_id = m.old_stage_id
        """)

    # Step 5: Add new foreign key constraint to stages table
    if dialect_name != "sqlite":
        op.create_foreign_key(
            'fk_student_progress_stage',
            'student_progress',
            'stages',
            ['current_stage_id'],
            ['id'],
            ondelete='RESTRICT'
        )


def downgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    # Step 1: Drop the new foreign key
    if dialect_name == "sqlite":
        with op.batch_alter_table("student_progress", recreate="always") as batch_op:
            batch_op.drop_constraint('fk_student_progress_stage', type_='foreignkey')
            batch_op.create_foreign_key(
                'fk_student_progress_direction_stage',
                'direction_stages',
                ['direction_id', 'current_stage_id'],
                ['direction_id', 'id'],
                ondelete='RESTRICT'
            )
    else:
        op.drop_constraint('fk_student_progress_stage', 'student_progress', type_='foreignkey')

    # Step 2: Recreate mapping table for reverse migration
    op.execute("""
        CREATE TEMP TABLE stage_id_mapping AS
        SELECT
            ds.id as old_stage_id,
            s.id as new_stage_id
        FROM direction_stages ds
        JOIN stages s ON s.direction_id = ds.direction_id AND s.stage_number = ds.order_index + 1
    """)

    # Step 3: Restore student_progress.current_stage_id to point to direction_stages
    if dialect_name == "sqlite":
        op.execute("""
            UPDATE student_progress
            SET current_stage_id = (
                SELECT m.old_stage_id
                FROM stage_id_mapping m
                WHERE m.new_stage_id = student_progress.current_stage_id
            )
            WHERE current_stage_id IN (
                SELECT new_stage_id FROM stage_id_mapping
            )
        """)
    else:
        op.execute("""
            UPDATE student_progress sp
            SET current_stage_id = m.old_stage_id
            FROM stage_id_mapping m
            WHERE sp.current_stage_id = m.new_stage_id
        """)

    # Step 4: Recreate the composite foreign key constraint
    if dialect_name != "sqlite":
        op.create_foreign_key(
            'fk_student_progress_direction_stage',
            'student_progress',
            'direction_stages',
            ['direction_id', 'current_stage_id'],
            ['direction_id', 'id'],
            ondelete='RESTRICT'
        )

    # Step 5: Delete migrated data from stages table
    # Only delete stages that were copied from direction_stages
    op.execute("""
        DELETE FROM stages s
        WHERE EXISTS (
            SELECT 1 FROM direction_stages ds
            WHERE ds.direction_id = s.direction_id
            AND ds.order_index + 1 = s.stage_number
        )
    """)
