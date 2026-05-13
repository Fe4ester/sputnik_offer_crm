"""Tests for MentorDeadlineService."""

import pytest
from datetime import date, timedelta

from sputnik_offer_crm.models import StudentStageProgress
from sputnik_offer_crm.services import (
    DeadlineStudentHasNoProgressError,
    DeadlineStudentNotFoundError,
    InvalidDeadlineDateError,
    MentorDeadlineService,
)

pytest_plugins = ["tests.fixtures.db_fixtures"]


class TestMentorDeadlineService:
    """Test mentor deadline service."""

    async def test_get_current_stage_deadline_with_deadline(
        self, db_session, student, direction, stage, student_progress, student_stage_progress
    ):
        """Test get current stage deadline when deadline is set."""
        # Set deadline
        deadline = date.today() + timedelta(days=7)
        student_stage_progress.planned_deadline = deadline
        await db_session.commit()

        service = MentorDeadlineService(db_session)
        current_stage, current_deadline = await service.get_current_stage_deadline(student.id)

        assert current_stage.id == stage.id
        assert current_deadline == deadline

    async def test_get_current_stage_deadline_without_deadline(
        self, db_session, student, direction, stage, student_progress, student_stage_progress
    ):
        """Test get current stage deadline when deadline is not set."""
        # Clear deadline if it was set by fixture
        student_stage_progress.planned_deadline = None
        await db_session.commit()

        service = MentorDeadlineService(db_session)
        current_stage, current_deadline = await service.get_current_stage_deadline(student.id)

        assert current_stage.id == stage.id
        assert current_deadline is None

    async def test_get_current_stage_deadline_no_stage_progress(
        self, db_session, student, direction, stage, student_progress
    ):
        """Test get current stage deadline when stage progress doesn't exist."""
        service = MentorDeadlineService(db_session)
        current_stage, current_deadline = await service.get_current_stage_deadline(student.id)

        assert current_stage.id == stage.id
        assert current_deadline is None

    async def test_get_current_stage_deadline_student_not_found(self, db_session):
        """Test get current stage deadline for non-existent student."""
        service = MentorDeadlineService(db_session)

        with pytest.raises(DeadlineStudentNotFoundError):
            await service.get_current_stage_deadline(999999)

    async def test_get_current_stage_deadline_no_progress(self, db_session, student):
        """Test get current stage deadline for student without progress."""
        service = MentorDeadlineService(db_session)

        with pytest.raises(DeadlineStudentHasNoProgressError):
            await service.get_current_stage_deadline(student.id)

    async def test_set_current_stage_deadline_new(
        self, db_session, student, direction, stage, student_progress
    ):
        """Test set deadline when stage progress doesn't exist."""
        from sqlalchemy import select

        deadline = date.today() + timedelta(days=7)

        service = MentorDeadlineService(db_session)
        result_stage = await service.set_current_stage_deadline(student.id, deadline)

        assert result_stage.id == stage.id

        # Verify stage progress created with deadline
        result = await db_session.execute(
            select(StudentStageProgress).where(
                StudentStageProgress.student_id == student.id,
                StudentStageProgress.stage_id == stage.id,
            )
        )
        stage_progress = result.scalar_one()
        assert stage_progress.planned_deadline == deadline
        assert stage_progress.status == "active"
        assert stage_progress.started_at == date.today()

    async def test_set_current_stage_deadline_update(
        self, db_session, student, direction, stage, student_progress, student_stage_progress
    ):
        """Test set deadline when stage progress already exists."""
        old_deadline = date.today() + timedelta(days=3)
        student_stage_progress.planned_deadline = old_deadline
        await db_session.commit()

        new_deadline = date.today() + timedelta(days=14)

        service = MentorDeadlineService(db_session)
        result_stage = await service.set_current_stage_deadline(student.id, new_deadline)

        assert result_stage.id == stage.id

        # Verify deadline updated
        await db_session.refresh(student_stage_progress)
        assert student_stage_progress.planned_deadline == new_deadline

    async def test_set_current_stage_deadline_student_not_found(self, db_session):
        """Test set deadline for non-existent student."""
        deadline = date.today() + timedelta(days=7)

        service = MentorDeadlineService(db_session)

        with pytest.raises(DeadlineStudentNotFoundError):
            await service.set_current_stage_deadline(999999, deadline)

    async def test_set_current_stage_deadline_no_progress(self, db_session, student):
        """Test set deadline for student without progress."""
        deadline = date.today() + timedelta(days=7)

        service = MentorDeadlineService(db_session)

        with pytest.raises(DeadlineStudentHasNoProgressError):
            await service.set_current_stage_deadline(student.id, deadline)

    async def test_set_current_stage_deadline_past_date(
        self, db_session, student, direction, stage, student_progress
    ):
        """Test set deadline with date in the past."""
        deadline = date.today() - timedelta(days=1)

        service = MentorDeadlineService(db_session)

        with pytest.raises(InvalidDeadlineDateError):
            await service.set_current_stage_deadline(student.id, deadline)

    async def test_set_current_stage_deadline_future(
        self, db_session, student, direction, stage, student_progress
    ):
        """Test set deadline with future date."""
        from sqlalchemy import select

        deadline = date.today() + timedelta(days=30)

        service = MentorDeadlineService(db_session)
        result_stage = await service.set_current_stage_deadline(student.id, deadline)

        assert result_stage.id == stage.id

        # Verify deadline set
        result = await db_session.execute(
            select(StudentStageProgress).where(
                StudentStageProgress.student_id == student.id,
                StudentStageProgress.stage_id == stage.id,
            )
        )
        stage_progress = result.scalar_one()
        assert stage_progress.planned_deadline == deadline

    async def test_set_current_stage_deadline_preserves_other_fields(
        self, db_session, student, direction, stage, student_progress, student_stage_progress
    ):
        """Test set deadline preserves other stage progress fields."""
        # Set initial state
        old_deadline = date.today() + timedelta(days=3)
        old_started_at = date.today() - timedelta(days=5)
        student_stage_progress.planned_deadline = old_deadline
        student_stage_progress.started_at = old_started_at
        student_stage_progress.status = "active"
        await db_session.commit()

        new_deadline = date.today() + timedelta(days=14)

        service = MentorDeadlineService(db_session)
        await service.set_current_stage_deadline(student.id, new_deadline)

        # Verify other fields preserved
        await db_session.refresh(student_stage_progress)
        assert student_stage_progress.planned_deadline == new_deadline
        assert student_stage_progress.started_at == old_started_at
        assert student_stage_progress.status == "active"

    async def test_set_current_stage_deadline_visible_in_student_deadlines(
        self, db_session, student, direction, stage, student_progress
    ):
        """Test that set deadline is visible in student deadlines view."""
        from sputnik_offer_crm.services import StudentService

        deadline = date.today() + timedelta(days=7)

        # Set deadline
        deadline_service = MentorDeadlineService(db_session)
        await deadline_service.set_current_stage_deadline(student.id, deadline)

        # Check it's visible in student deadlines
        student_service = StudentService(db_session)
        deadlines = await student_service.get_student_deadlines(student.telegram_id)

        # Should have stage deadline with "Этап: " prefix
        stage_deadlines = [d for d in deadlines if d.title == f"Этап: {stage.title}"]
        assert len(stage_deadlines) == 1
        assert stage_deadlines[0].deadline_date == deadline
        assert not stage_deadlines[0].is_overdue
