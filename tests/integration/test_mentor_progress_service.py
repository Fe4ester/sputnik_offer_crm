"""Tests for MentorProgressService."""

import pytest

from sputnik_offer_crm.models import StudentStageProgress
from sputnik_offer_crm.services import (
    AlreadyOnFinalStageError,
    MentorProgressService,
    NextStageNotFoundError,
    StudentHasNoProgressError,
    StudentNotFoundError,
)

pytest_plugins = ["tests.fixtures.db_fixtures"]


class TestMentorProgressService:
    """Test mentor progress service."""

    async def test_get_next_stage_info_success(
        self, db_session, student, direction, stage, student_progress
    ):
        """Test get next stage info with valid data."""
        from sputnik_offer_crm.models import Stage

        # Create next stage
        next_stage = Stage(
            direction_id=direction.id,
            stage_number=stage.stage_number + 1,
            title="Next Stage",
            is_active=True,
        )
        db_session.add(next_stage)
        await db_session.commit()

        service = MentorProgressService(db_session)
        info = await service.get_next_stage_info(student.id)

        assert info.current_stage.id == stage.id
        assert info.next_stage.id == next_stage.id
        assert info.student.id == student.id

    async def test_get_next_stage_info_student_not_found(self, db_session):
        """Test get next stage info for non-existent student."""
        service = MentorProgressService(db_session)

        with pytest.raises(StudentNotFoundError):
            await service.get_next_stage_info(999999)

    async def test_get_next_stage_info_no_progress(self, db_session, student):
        """Test get next stage info for student without progress."""
        service = MentorProgressService(db_session)

        with pytest.raises(StudentHasNoProgressError):
            await service.get_next_stage_info(student.id)

    async def test_get_next_stage_info_on_final_stage(
        self, db_session, student, direction, stage, student_progress
    ):
        """Test get next stage info when student is on final stage."""
        service = MentorProgressService(db_session)

        with pytest.raises(AlreadyOnFinalStageError):
            await service.get_next_stage_info(student.id)

    async def test_get_next_stage_info_next_stage_inactive(
        self, db_session, student, direction, stage, student_progress
    ):
        """Test get next stage info when next stage is inactive."""
        from sputnik_offer_crm.models import Stage

        # Create inactive next stage
        next_stage = Stage(
            direction_id=direction.id,
            stage_number=stage.stage_number + 1,
            title="Inactive Next Stage",
            is_active=False,
        )
        db_session.add(next_stage)
        await db_session.commit()

        service = MentorProgressService(db_session)

        with pytest.raises(AlreadyOnFinalStageError):
            await service.get_next_stage_info(student.id)

    async def test_get_next_stage_info_gap_in_stage_numbers(
        self, db_session, student, direction, stage, student_progress
    ):
        """Test get next stage info when there's a gap in stage numbers."""
        from sputnik_offer_crm.models import Stage

        # Create stage with gap (stage_number + 2 instead of + 1)
        next_stage = Stage(
            direction_id=direction.id,
            stage_number=stage.stage_number + 2,
            title="Stage After Gap",
            is_active=True,
        )
        db_session.add(next_stage)
        await db_session.commit()

        service = MentorProgressService(db_session)

        with pytest.raises(NextStageNotFoundError):
            await service.get_next_stage_info(student.id)

    async def test_move_to_next_stage_success(
        self, db_session, student, direction, stage, student_progress
    ):
        """Test successful move to next stage."""
        from datetime import date

        from sqlalchemy import select

        from sputnik_offer_crm.models import Stage, StudentProgress

        # Create next stage
        next_stage = Stage(
            direction_id=direction.id,
            stage_number=stage.stage_number + 1,
            title="Next Stage",
            is_active=True,
        )
        db_session.add(next_stage)
        await db_session.commit()

        service = MentorProgressService(db_session)
        result_stage = await service.move_to_next_stage(student.id)

        assert result_stage.id == next_stage.id

        # Verify StudentProgress updated
        result = await db_session.execute(
            select(StudentProgress).where(StudentProgress.student_id == student.id)
        )
        progress = result.scalar_one()
        assert progress.current_stage_id == next_stage.id

    async def test_move_to_next_stage_marks_current_as_done(
        self, db_session, student, direction, stage, student_progress, student_stage_progress
    ):
        """Test move to next stage marks current stage progress as done."""
        from datetime import date

        from sqlalchemy import select

        from sputnik_offer_crm.models import Stage

        # Create next stage
        next_stage = Stage(
            direction_id=direction.id,
            stage_number=stage.stage_number + 1,
            title="Next Stage",
            is_active=True,
        )
        db_session.add(next_stage)
        await db_session.commit()

        service = MentorProgressService(db_session)
        await service.move_to_next_stage(student.id)

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

    async def test_move_to_next_stage_creates_next_stage_progress(
        self, db_session, student, direction, stage, student_progress
    ):
        """Test move to next stage creates next stage progress record."""
        from datetime import date

        from sqlalchemy import select

        from sputnik_offer_crm.models import Stage

        # Create next stage
        next_stage = Stage(
            direction_id=direction.id,
            stage_number=stage.stage_number + 1,
            title="Next Stage",
            is_active=True,
        )
        db_session.add(next_stage)
        await db_session.commit()

        service = MentorProgressService(db_session)
        await service.move_to_next_stage(student.id)

        # Verify next stage progress created
        result = await db_session.execute(
            select(StudentStageProgress).where(
                StudentStageProgress.student_id == student.id,
                StudentStageProgress.stage_id == next_stage.id,
            )
        )
        next_progress = result.scalar_one()
        assert next_progress.status == "active"
        assert next_progress.started_at == date.today()

    async def test_move_to_next_stage_updates_existing_next_stage_progress(
        self, db_session, student, direction, stage, student_progress
    ):
        """Test move to next stage updates existing next stage progress."""
        from datetime import date

        from sqlalchemy import select

        from sputnik_offer_crm.models import Stage

        # Create next stage
        next_stage = Stage(
            direction_id=direction.id,
            stage_number=stage.stage_number + 1,
            title="Next Stage",
            is_active=True,
        )
        db_session.add(next_stage)
        await db_session.flush()

        # Create existing next stage progress (not_started)
        existing_progress = StudentStageProgress(
            student_id=student.id,
            stage_id=next_stage.id,
            status="not_started",
        )
        db_session.add(existing_progress)
        await db_session.commit()

        service = MentorProgressService(db_session)
        await service.move_to_next_stage(student.id)

        # Verify existing progress updated
        await db_session.refresh(existing_progress)
        assert existing_progress.status == "active"
        assert existing_progress.started_at == date.today()

    async def test_move_to_next_stage_student_not_found(self, db_session):
        """Test move to next stage for non-existent student."""
        service = MentorProgressService(db_session)

        with pytest.raises(StudentNotFoundError):
            await service.move_to_next_stage(999999)

    async def test_move_to_next_stage_no_progress(self, db_session, student):
        """Test move to next stage for student without progress."""
        service = MentorProgressService(db_session)

        with pytest.raises(StudentHasNoProgressError):
            await service.move_to_next_stage(student.id)

    async def test_move_to_next_stage_on_final_stage(
        self, db_session, student, direction, stage, student_progress
    ):
        """Test move to next stage when student is on final stage."""
        service = MentorProgressService(db_session)

        with pytest.raises(AlreadyOnFinalStageError):
            await service.move_to_next_stage(student.id)

    async def test_move_to_next_stage_idempotent(
        self, db_session, student, direction, stage, student_progress
    ):
        """Test move to next stage is safe to call multiple times."""
        from sqlalchemy import select

        from sputnik_offer_crm.models import Stage, StudentProgress

        # Create next stage
        next_stage = Stage(
            direction_id=direction.id,
            stage_number=stage.stage_number + 1,
            title="Next Stage",
            is_active=True,
        )
        db_session.add(next_stage)
        await db_session.commit()

        service = MentorProgressService(db_session)

        # First move
        await service.move_to_next_stage(student.id)

        # Verify moved
        result = await db_session.execute(
            select(StudentProgress).where(StudentProgress.student_id == student.id)
        )
        progress = result.scalar_one()
        assert progress.current_stage_id == next_stage.id

        # Second move should fail with AlreadyOnFinalStageError
        # (since there's no stage after next_stage)
        with pytest.raises(AlreadyOnFinalStageError):
            await service.move_to_next_stage(student.id)

    async def test_move_to_next_stage_preserves_started_at(
        self, db_session, student, direction, stage, student_progress
    ):
        """Test move to next stage preserves started_at if already set."""
        from datetime import date, timedelta

        from sqlalchemy import select

        from sputnik_offer_crm.models import Stage

        # Create next stage
        next_stage = Stage(
            direction_id=direction.id,
            stage_number=stage.stage_number + 1,
            title="Next Stage",
            is_active=True,
        )
        db_session.add(next_stage)
        await db_session.flush()

        # Create existing next stage progress with old started_at
        old_date = date.today() - timedelta(days=10)
        existing_progress = StudentStageProgress(
            student_id=student.id,
            stage_id=next_stage.id,
            status="not_started",
            started_at=old_date,
        )
        db_session.add(existing_progress)
        await db_session.commit()

        service = MentorProgressService(db_session)
        await service.move_to_next_stage(student.id)

        # Verify started_at preserved
        await db_session.refresh(existing_progress)
        assert existing_progress.started_at == old_date
