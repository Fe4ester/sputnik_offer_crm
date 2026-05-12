"""Tests for MentorProgressService manual stage selection."""

import pytest

from sputnik_offer_crm.models import StudentStageProgress
from sputnik_offer_crm.services import (
    AlreadyOnThisStageError,
    MentorProgressService,
    StageNotFoundError,
    StageNotInDirectionError,
    StudentHasNoProgressError,
    StudentNotFoundError,
)

pytest_plugins = ["tests.fixtures.db_fixtures"]


class TestMentorProgressManualStage:
    """Test mentor progress manual stage selection."""

    async def test_get_available_stages_success(
        self, db_session, student, direction, stage, student_progress
    ):
        """Test get available stages for student."""
        from sputnik_offer_crm.models import Stage

        # Create additional stages
        stage2 = Stage(
            direction_id=direction.id,
            stage_number=stage.stage_number + 1,
            title="Stage 2",
            is_active=True,
        )
        stage3 = Stage(
            direction_id=direction.id,
            stage_number=stage.stage_number + 2,
            title="Stage 3",
            is_active=True,
        )
        db_session.add_all([stage2, stage3])
        await db_session.commit()

        service = MentorProgressService(db_session)
        stages = await service.get_available_stages(student.id)

        assert len(stages) == 3
        assert stages[0].id == stage.id
        assert stages[1].id == stage2.id
        assert stages[2].id == stage3.id

    async def test_get_available_stages_only_active(
        self, db_session, student, direction, stage, student_progress
    ):
        """Test get available stages returns only active stages."""
        from sputnik_offer_crm.models import Stage

        # Create active and inactive stages
        stage2 = Stage(
            direction_id=direction.id,
            stage_number=stage.stage_number + 1,
            title="Active Stage",
            is_active=True,
        )
        stage3 = Stage(
            direction_id=direction.id,
            stage_number=stage.stage_number + 2,
            title="Inactive Stage",
            is_active=False,
        )
        db_session.add_all([stage2, stage3])
        await db_session.commit()

        service = MentorProgressService(db_session)
        stages = await service.get_available_stages(student.id)

        assert len(stages) == 2
        assert all(s.is_active for s in stages)

    async def test_get_available_stages_student_not_found(self, db_session):
        """Test get available stages for non-existent student."""
        service = MentorProgressService(db_session)

        with pytest.raises(StudentNotFoundError):
            await service.get_available_stages(999999)

    async def test_get_available_stages_no_progress(self, db_session, student):
        """Test get available stages for student without progress."""
        service = MentorProgressService(db_session)

        with pytest.raises(StudentHasNoProgressError):
            await service.get_available_stages(student.id)

    async def test_move_to_stage_forward(
        self, db_session, student, direction, stage, student_progress
    ):
        """Test move to stage forward (to later stage)."""
        from datetime import date

        from sqlalchemy import select

        from sputnik_offer_crm.models import Stage, StudentProgress

        # Create target stage
        target_stage = Stage(
            direction_id=direction.id,
            stage_number=stage.stage_number + 2,
            title="Target Stage",
            is_active=True,
        )
        db_session.add(target_stage)
        await db_session.commit()

        service = MentorProgressService(db_session)
        result_stage = await service.move_to_stage(student.id, target_stage.id)

        assert result_stage.id == target_stage.id

        # Verify StudentProgress updated
        result = await db_session.execute(
            select(StudentProgress).where(StudentProgress.student_id == student.id)
        )
        progress = result.scalar_one()
        assert progress.current_stage_id == target_stage.id

    async def test_move_to_stage_backward(
        self, db_session, student, direction, stage, student_progress
    ):
        """Test move to stage backward (to earlier stage)."""
        from sqlalchemy import select

        from sputnik_offer_crm.models import Stage, StudentProgress

        # Create stages
        stage2 = Stage(
            direction_id=direction.id,
            stage_number=stage.stage_number + 1,
            title="Stage 2",
            is_active=True,
        )
        stage3 = Stage(
            direction_id=direction.id,
            stage_number=stage.stage_number + 2,
            title="Stage 3",
            is_active=True,
        )
        db_session.add_all([stage2, stage3])
        await db_session.commit()

        # Move student to stage3
        student_progress.current_stage_id = stage3.id
        await db_session.commit()

        # Move back to stage2
        service = MentorProgressService(db_session)
        result_stage = await service.move_to_stage(student.id, stage2.id)

        assert result_stage.id == stage2.id

        # Verify StudentProgress updated
        result = await db_session.execute(
            select(StudentProgress).where(StudentProgress.student_id == student.id)
        )
        progress = result.scalar_one()
        assert progress.current_stage_id == stage2.id

    async def test_move_to_stage_marks_current_as_done(
        self, db_session, student, direction, stage, student_progress, student_stage_progress
    ):
        """Test move to stage marks current stage progress as done."""
        from datetime import date

        from sqlalchemy import select

        from sputnik_offer_crm.models import Stage

        # Create target stage
        target_stage = Stage(
            direction_id=direction.id,
            stage_number=stage.stage_number + 1,
            title="Target Stage",
            is_active=True,
        )
        db_session.add(target_stage)
        await db_session.commit()

        service = MentorProgressService(db_session)
        await service.move_to_stage(student.id, target_stage.id)

        # Verify current stage progress marked as done
        result = await db_session.execute(
            select(StudentStageProgress).where(
                StudentStageProgress.student_id == student.id,
                StudentStageProgress.stage_id == stage.id,
            )
        )
        current_progress = result.scalar_one()
        assert current_progress.status == "done"
        assert current_progress.completed_at == date.today()

    async def test_move_to_stage_creates_target_stage_progress(
        self, db_session, student, direction, stage, student_progress
    ):
        """Test move to stage creates target stage progress record."""
        from datetime import date

        from sqlalchemy import select

        from sputnik_offer_crm.models import Stage

        # Create target stage
        target_stage = Stage(
            direction_id=direction.id,
            stage_number=stage.stage_number + 1,
            title="Target Stage",
            is_active=True,
        )
        db_session.add(target_stage)
        await db_session.commit()

        service = MentorProgressService(db_session)
        await service.move_to_stage(student.id, target_stage.id)

        # Verify target stage progress created
        result = await db_session.execute(
            select(StudentStageProgress).where(
                StudentStageProgress.student_id == student.id,
                StudentStageProgress.stage_id == target_stage.id,
            )
        )
        target_progress = result.scalar_one()
        assert target_progress.status == "active"
        assert target_progress.started_at == date.today()

    async def test_move_to_stage_updates_existing_target_progress(
        self, db_session, student, direction, stage, student_progress
    ):
        """Test move to stage updates existing target stage progress."""
        from datetime import date

        from sqlalchemy import select

        from sputnik_offer_crm.models import Stage

        # Create target stage
        target_stage = Stage(
            direction_id=direction.id,
            stage_number=stage.stage_number + 1,
            title="Target Stage",
            is_active=True,
        )
        db_session.add(target_stage)
        await db_session.flush()

        # Create existing target stage progress (not_started)
        existing_progress = StudentStageProgress(
            student_id=student.id,
            stage_id=target_stage.id,
            status="not_started",
        )
        db_session.add(existing_progress)
        await db_session.commit()

        service = MentorProgressService(db_session)
        await service.move_to_stage(student.id, target_stage.id)

        # Verify existing progress updated
        await db_session.refresh(existing_progress)
        assert existing_progress.status == "active"
        assert existing_progress.started_at == date.today()

    async def test_move_to_stage_student_not_found(self, db_session):
        """Test move to stage for non-existent student."""
        service = MentorProgressService(db_session)

        with pytest.raises(StudentNotFoundError):
            await service.move_to_stage(999999, 1)

    async def test_move_to_stage_no_progress(self, db_session, student):
        """Test move to stage for student without progress."""
        service = MentorProgressService(db_session)

        with pytest.raises(StudentHasNoProgressError):
            await service.move_to_stage(student.id, 1)

    async def test_move_to_stage_stage_not_found(
        self, db_session, student, direction, stage, student_progress
    ):
        """Test move to stage with non-existent stage."""
        service = MentorProgressService(db_session)

        with pytest.raises(StageNotFoundError):
            await service.move_to_stage(student.id, 999999)

    async def test_move_to_stage_wrong_direction(
        self, db_session, student, direction, stage, student_progress
    ):
        """Test move to stage with stage from different direction."""
        from sputnik_offer_crm.models import Direction, Stage

        # Create another direction and stage
        other_direction = Direction(
            code="other",
            name="Other Direction",
            is_active=True,
        )
        db_session.add(other_direction)
        await db_session.flush()

        other_stage = Stage(
            direction_id=other_direction.id,
            stage_number=1,
            title="Other Stage",
            is_active=True,
        )
        db_session.add(other_stage)
        await db_session.commit()

        service = MentorProgressService(db_session)

        with pytest.raises(StageNotInDirectionError):
            await service.move_to_stage(student.id, other_stage.id)

    async def test_move_to_stage_already_on_stage(
        self, db_session, student, direction, stage, student_progress
    ):
        """Test move to stage when already on that stage."""
        service = MentorProgressService(db_session)

        with pytest.raises(AlreadyOnThisStageError):
            await service.move_to_stage(student.id, stage.id)

    async def test_move_to_stage_preserves_started_at(
        self, db_session, student, direction, stage, student_progress
    ):
        """Test move to stage preserves started_at if already set."""
        from datetime import date, timedelta

        from sputnik_offer_crm.models import Stage

        # Create target stage
        target_stage = Stage(
            direction_id=direction.id,
            stage_number=stage.stage_number + 1,
            title="Target Stage",
            is_active=True,
        )
        db_session.add(target_stage)
        await db_session.flush()

        # Create existing target stage progress with old started_at
        old_date = date.today() - timedelta(days=10)
        existing_progress = StudentStageProgress(
            student_id=student.id,
            stage_id=target_stage.id,
            status="done",
            started_at=old_date,
        )
        db_session.add(existing_progress)
        await db_session.commit()

        service = MentorProgressService(db_session)
        await service.move_to_stage(student.id, target_stage.id)

        # Verify started_at preserved
        await db_session.refresh(existing_progress)
        assert existing_progress.started_at == old_date
