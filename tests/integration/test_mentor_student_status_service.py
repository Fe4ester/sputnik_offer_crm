"""Integration tests for mentor student status service."""

import pytest
from sqlalchemy import select

from sputnik_offer_crm.models import Student, StudentProgress
from sputnik_offer_crm.services import (
    MentorStudentStatusService,
    StudentAlreadyInactiveError,
    StatusStudentNotFoundError,
)

pytest_plugins = ["tests.fixtures.db_fixtures"]


class TestMentorStudentStatusService:
    """Test mentor student status service."""

    async def test_dropout_student_success(self, db_session, student, student_progress):
        """Test successful student dropout."""
        service = MentorStudentStatusService(db_session)

        # Verify student is active before dropout
        assert student.is_active is True

        # Dropout student
        updated_student = await service.dropout_student(student.id)

        # Verify student is now inactive
        assert updated_student.is_active is False
        assert updated_student.id == student.id

        # Verify change persisted in database
        result = await db_session.execute(
            select(Student).where(Student.id == student.id)
        )
        db_student = result.scalar_one()
        assert db_student.is_active is False

    async def test_dropout_student_not_found(self, db_session):
        """Test dropout with non-existent student."""
        service = MentorStudentStatusService(db_session)

        with pytest.raises(StatusStudentNotFoundError, match="Student 99999 not found"):
            await service.dropout_student(99999)

    async def test_dropout_student_already_inactive(self, db_session, student):
        """Test dropout when student is already inactive."""
        service = MentorStudentStatusService(db_session)

        # First dropout
        await service.dropout_student(student.id)

        # Try to dropout again
        with pytest.raises(
            StudentAlreadyInactiveError,
            match=f"Student {student.id} is already inactive",
        ):
            await service.dropout_student(student.id)

    async def test_dropout_preserves_progress_data(
        self, db_session, student, student_progress
    ):
        """Test that dropout preserves all progress data."""
        service = MentorStudentStatusService(db_session)

        # Store original progress data
        original_progress_id = student_progress.id
        original_current_stage_id = student_progress.current_stage_id
        original_started_at = student_progress.started_at

        # Dropout student
        await service.dropout_student(student.id)

        # Verify progress still exists and unchanged
        result = await db_session.execute(
            select(StudentProgress).where(StudentProgress.student_id == student.id)
        )
        progress = result.scalar_one()

        assert progress.id == original_progress_id
        assert progress.current_stage_id == original_current_stage_id
        assert progress.started_at == original_started_at
        assert progress.student_id == student.id

    async def test_dropout_preserves_student_data(self, db_session, student):
        """Test that dropout preserves all student data except is_active."""
        service = MentorStudentStatusService(db_session)

        # Store original student data
        original_telegram_id = student.telegram_id
        original_first_name = student.first_name
        original_last_name = student.last_name
        original_username = student.username
        original_timezone = student.timezone

        # Dropout student
        await service.dropout_student(student.id)

        # Verify all data preserved except is_active
        result = await db_session.execute(
            select(Student).where(Student.id == student.id)
        )
        student_obj = result.scalar_one()

        assert student_obj.telegram_id == original_telegram_id
        assert student_obj.first_name == original_first_name
        assert student_obj.last_name == original_last_name
        assert student_obj.username == original_username
        assert student_obj.timezone == original_timezone
        assert student_obj.is_active is False  # Only this changed
