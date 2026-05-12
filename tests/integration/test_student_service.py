"""Tests for StudentService."""

from datetime import date

import pytest
from freezegun import freeze_time

from sputnik_offer_crm.services import StudentService

pytest_plugins = ["tests.fixtures.db_fixtures"]


class TestStudentService:
    """Test student service."""

    async def test_get_student_progress_success(
        self, db_session, student, direction, stage, student_progress
    ):
        """Test get student progress success."""
        service = StudentService(db_session)

        result = await service.get_student_progress(student.telegram_id)

        assert result is not None
        assert result.student.id == student.id
        assert result.direction.id == direction.id
        assert result.current_stage.id == stage.id
        assert result.progress.id == student_progress.id

    async def test_get_student_progress_student_not_found(self, db_session):
        """Test get student progress when student not found."""
        service = StudentService(db_session)

        result = await service.get_student_progress(999999999)

        assert result is None

    async def test_get_student_progress_no_progress(self, db_session, student):
        """Test get student progress when student has no progress."""
        service = StudentService(db_session)

        result = await service.get_student_progress(student.telegram_id)

        assert result is None

    @freeze_time("2026-05-15")
    async def test_get_student_deadlines_with_stage_and_task(
        self, db_session, student, stage, student_stage_progress, student_task
    ):
        """Test get student deadlines with both stage and task deadlines."""
        service = StudentService(db_session)

        deadlines = await service.get_student_deadlines(student.telegram_id)

        assert len(deadlines) == 2

        # Check stage deadline
        stage_deadline = next(d for d in deadlines if d.deadline_type == "stage")
        assert stage_deadline.title == f"Этап: {stage.title}"
        assert stage_deadline.deadline_date == date(2026, 6, 1)
        assert stage_deadline.is_overdue is False
        assert stage_deadline.stage_name == stage.title

        # Check task deadline
        task_deadline = next(d for d in deadlines if d.deadline_type == "task")
        assert task_deadline.title == student_task.title
        assert task_deadline.deadline_date == date(2026, 5, 20)
        assert task_deadline.is_overdue is False
        assert task_deadline.task_id == student_task.id

    @freeze_time("2026-05-15")
    async def test_get_student_deadlines_sorted_by_date(
        self, db_session, student, stage, student_stage_progress, student_task
    ):
        """Test that deadlines are sorted by date."""
        service = StudentService(db_session)

        deadlines = await service.get_student_deadlines(student.telegram_id)

        # Task deadline (2026-05-20) should come before stage deadline (2026-06-01)
        assert deadlines[0].deadline_date == date(2026, 5, 20)
        assert deadlines[1].deadline_date == date(2026, 6, 1)

    @freeze_time("2026-06-15")
    async def test_get_student_deadlines_overdue_detection(
        self, db_session, student, stage, student_stage_progress, student_task
    ):
        """Test overdue deadline detection."""
        service = StudentService(db_session)

        deadlines = await service.get_student_deadlines(student.telegram_id)

        # Both deadlines should be overdue
        assert all(d.is_overdue for d in deadlines)

    async def test_get_student_deadlines_empty(self, db_session, student):
        """Test get student deadlines when no deadlines exist."""
        service = StudentService(db_session)

        deadlines = await service.get_student_deadlines(student.telegram_id)

        assert len(deadlines) == 0

    async def test_get_student_deadlines_student_not_found(self, db_session):
        """Test get student deadlines when student not found."""
        service = StudentService(db_session)

        deadlines = await service.get_student_deadlines(999999999)

        assert len(deadlines) == 0

    async def test_get_student_deadlines_excludes_completed_tasks(
        self, db_session, student, student_task
    ):
        """Test that completed tasks are excluded from deadlines."""
        from datetime import datetime, timezone

        # Mark task as completed
        student_task.completed_at = datetime.now(timezone.utc)
        await db_session.commit()

        service = StudentService(db_session)

        deadlines = await service.get_student_deadlines(student.telegram_id)

        # Should not include completed task
        assert len(deadlines) == 0

    async def test_get_student_deadlines_excludes_tasks_without_deadline(
        self, db_session, student
    ):
        """Test that tasks without deadline are excluded."""
        from sputnik_offer_crm.models import StudentTask

        task = StudentTask(
            student_id=student.id,
            task_order=1,
            title="Задача без дедлайна",
            deadline=None,
            status="open",
        )
        db_session.add(task)
        await db_session.commit()

        service = StudentService(db_session)

        deadlines = await service.get_student_deadlines(student.telegram_id)

        assert len(deadlines) == 0

    async def test_get_student_deadlines_excludes_stages_without_deadline(
        self, db_session, student, stage
    ):
        """Test that stage progress without deadline is excluded."""
        from sputnik_offer_crm.models import StudentStageProgress

        progress = StudentStageProgress(
            student_id=student.id,
            stage_id=stage.id,
            status="active",
            planned_deadline=None,
        )
        db_session.add(progress)
        await db_session.commit()

        service = StudentService(db_session)

        deadlines = await service.get_student_deadlines(student.telegram_id)

        assert len(deadlines) == 0
