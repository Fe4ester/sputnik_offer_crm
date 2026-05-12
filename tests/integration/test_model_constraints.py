"""Tests for database models constraints."""

from datetime import date, datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from sputnik_offer_crm.models import (
    Direction,
    DirectionStage,
    InviteCode,
    Stage,
    Student,
    StudentStageProgress,
    StudentTask,
)

pytest_plugins = ["tests.fixtures.db_fixtures"]


class TestInviteCodeConstraints:
    """Test InviteCode model constraints."""

    async def test_code_uniqueness(self, db_session, mentor, direction):
        """Test that invite codes must be unique."""
        code1 = InviteCode(
            code="UNIQUE01",
            mentor_id=mentor.id,
            direction_id=direction.id,
            suggested_timezone="Europe/Moscow",
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(code1)
        await db_session.commit()

        code2 = InviteCode(
            code="UNIQUE01",
            mentor_id=mentor.id,
            direction_id=direction.id,
            suggested_timezone="Europe/Moscow",
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(code2)

        with pytest.raises(IntegrityError):
            await db_session.commit()

    async def test_code_length_constraint_too_short(self, db_session, mentor, direction):
        """Test that code length minimum is enforced."""
        code_short = InviteCode(
            code="ABC",
            mentor_id=mentor.id,
            direction_id=direction.id,
            suggested_timezone="Europe/Moscow",
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(code_short)

        with pytest.raises(IntegrityError):
            await db_session.commit()

    async def test_code_length_constraint_too_long(self, db_session, mentor, direction):
        """Test that code length maximum is enforced."""
        code_long = InviteCode(
            code="A" * 25,
            mentor_id=mentor.id,
            direction_id=direction.id,
            suggested_timezone="Europe/Moscow",
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(code_long)

        with pytest.raises(IntegrityError):
            await db_session.commit()


class TestStudentConstraints:
    """Test Student model constraints."""

    async def test_telegram_id_uniqueness(self, db_session):
        """Test that telegram_id must be unique."""
        student1 = Student(
            telegram_id=111222333,
            first_name="User1",
            timezone="Europe/Moscow",
        )
        db_session.add(student1)
        await db_session.commit()

        student2 = Student(
            telegram_id=111222333,
            first_name="User2",
            timezone="Europe/London",
        )
        db_session.add(student2)

        with pytest.raises(IntegrityError):
            await db_session.commit()


class TestDirectionStageConstraints:
    """Test DirectionStage model constraints."""

    async def test_order_index_uniqueness_per_direction(self, db_session, direction):
        """Test that order_index must be unique per direction."""
        stage1 = DirectionStage(
            direction_id=direction.id,
            name="Stage 1",
            order_index=0,
        )
        db_session.add(stage1)
        await db_session.commit()

        stage2 = DirectionStage(
            direction_id=direction.id,
            name="Stage 2",
            order_index=0,
        )
        db_session.add(stage2)

        with pytest.raises(IntegrityError):
            await db_session.commit()

    async def test_order_index_non_negative(self, db_session, direction):
        """Test that order_index must be non-negative."""
        stage = DirectionStage(
            direction_id=direction.id,
            name="Stage",
            order_index=-1,
        )
        db_session.add(stage)

        with pytest.raises(IntegrityError):
            await db_session.commit()


class TestStageConstraints:
    """Test Stage model constraints."""

    async def test_stage_number_uniqueness_per_direction(self, db_session, direction):
        """Test that stage_number must be unique per direction."""
        stage1 = Stage(
            direction_id=direction.id,
            stage_number=1,
            title="Stage 1",
        )
        db_session.add(stage1)
        await db_session.commit()

        stage2 = Stage(
            direction_id=direction.id,
            stage_number=1,
            title="Stage 2",
        )
        db_session.add(stage2)

        with pytest.raises(IntegrityError):
            await db_session.commit()

    async def test_stage_number_positive(self, db_session, direction):
        """Test that stage_number must be positive."""
        stage = Stage(
            direction_id=direction.id,
            stage_number=0,
            title="Stage",
        )
        db_session.add(stage)

        with pytest.raises(IntegrityError):
            await db_session.commit()

    async def test_planned_duration_positive_or_null(self, db_session, direction):
        """Test that planned_duration_days must be positive or null."""
        stage = Stage(
            direction_id=direction.id,
            stage_number=1,
            title="Stage",
            planned_duration_days=-5,
        )
        db_session.add(stage)

        with pytest.raises(IntegrityError):
            await db_session.commit()


class TestStudentStageProgressConstraints:
    """Test StudentStageProgress model constraints."""

    async def test_student_stage_uniqueness(self, db_session, student, stage):
        """Test that student can have only one progress per stage."""
        progress1 = StudentStageProgress(
            student_id=student.id,
            stage_id=stage.id,
            status="active",
        )
        db_session.add(progress1)
        await db_session.commit()

        progress2 = StudentStageProgress(
            student_id=student.id,
            stage_id=stage.id,
            status="done",
        )
        db_session.add(progress2)

        with pytest.raises(IntegrityError):
            await db_session.commit()

    async def test_completed_after_started(self, db_session, student, stage):
        """Test that completed_at must be >= started_at."""
        progress = StudentStageProgress(
            student_id=student.id,
            stage_id=stage.id,
            status="done",
            started_at=date(2026, 5, 10),
            completed_at=date(2026, 5, 5),
        )
        db_session.add(progress)

        with pytest.raises(IntegrityError):
            await db_session.commit()


class TestStudentTaskConstraints:
    """Test StudentTask model constraints."""

    async def test_task_order_positive_or_null(self, db_session, student):
        """Test that task_order must be positive or null."""
        task = StudentTask(
            student_id=student.id,
            title="Task",
            task_order=0,
            status="open",
        )
        db_session.add(task)

        with pytest.raises(IntegrityError):
            await db_session.commit()
