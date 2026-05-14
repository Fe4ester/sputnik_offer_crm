"""Tests for MentorDeadlineService bulk deadline setup."""

import pytest
from datetime import date, timedelta

from sputnik_offer_crm.models import StudentStageProgress
from sputnik_offer_crm.services import (
    DeadlineStudentHasNoProgressError,
    DeadlineStudentNotFoundError,
    MentorDeadlineService,
    NoStagesFoundError,
)

pytest_plugins = ["tests.fixtures.db_fixtures"]


class TestMentorDeadlineBulkSetup:
    """Test mentor deadline bulk setup."""

    async def test_calculate_all_stage_deadlines_single_stage(
        self, db_session, student, direction, stage, student_progress
    ):
        """Test calculate deadlines with single stage."""
        # Set planned duration
        stage.planned_duration_days = 7
        await db_session.commit()

        service = MentorDeadlineService(db_session)
        student_result, direction_result, previews = await service.calculate_all_stage_deadlines(
            student.id
        )

        assert student_result.id == student.id
        assert direction_result.id == direction.id
        assert len(previews) == 1
        assert previews[0].stage.id == stage.id
        assert previews[0].calculated_deadline == date.today() + timedelta(days=7)

    async def test_calculate_all_stage_deadlines_multiple_stages(
        self, db_session, student, direction, stage, student_progress
    ):
        """Test calculate deadlines with multiple stages."""
        from sputnik_offer_crm.models import Stage

        # Set planned duration for first stage
        stage.planned_duration_days = 7
        await db_session.commit()

        # Create additional stages
        stage2 = Stage(
            direction_id=direction.id,
            stage_number=stage.stage_number + 1,
            title="Stage 2",
            planned_duration_days=10,
            is_active=True,
        )
        stage3 = Stage(
            direction_id=direction.id,
            stage_number=stage.stage_number + 2,
            title="Stage 3",
            planned_duration_days=14,
            is_active=True,
        )
        db_session.add_all([stage2, stage3])
        await db_session.commit()

        service = MentorDeadlineService(db_session)
        _, _, previews = await service.calculate_all_stage_deadlines(student.id)

        assert len(previews) == 3

        # First stage: today + 7 days
        assert previews[0].stage.id == stage.id
        assert previews[0].calculated_deadline == date.today() + timedelta(days=7)

        # Second stage: first deadline + 10 days
        assert previews[1].stage.id == stage2.id
        assert previews[1].calculated_deadline == date.today() + timedelta(days=17)

        # Third stage: second deadline + 14 days
        assert previews[2].stage.id == stage3.id
        assert previews[2].calculated_deadline == date.today() + timedelta(days=31)

    async def test_calculate_all_stage_deadlines_uses_default_duration(
        self, db_session, student, direction, stage, student_progress
    ):
        """Test calculate deadlines uses default duration when planned_duration_days is None."""
        from sputnik_offer_crm.models import Stage

        # First stage has no planned duration
        stage.planned_duration_days = None
        await db_session.commit()

        # Create second stage with planned duration
        stage2 = Stage(
            direction_id=direction.id,
            stage_number=stage.stage_number + 1,
            title="Stage 2",
            planned_duration_days=10,
            is_active=True,
        )
        db_session.add(stage2)
        await db_session.commit()

        service = MentorDeadlineService(db_session)
        _, _, previews = await service.calculate_all_stage_deadlines(
            student.id, default_duration_days=14
        )

        assert len(previews) == 2

        # First stage uses default (14 days)
        assert previews[0].calculated_deadline == date.today() + timedelta(days=14)

        # Second stage uses its planned duration (10 days after first deadline)
        assert previews[1].calculated_deadline == date.today() + timedelta(days=24)

    async def test_calculate_all_stage_deadlines_only_active_stages(
        self, db_session, student, direction, stage, student_progress
    ):
        """Test calculate deadlines includes only active stages."""
        from sputnik_offer_crm.models import Stage

        stage.planned_duration_days = 7
        await db_session.commit()

        # Create active and inactive stages
        stage2 = Stage(
            direction_id=direction.id,
            stage_number=stage.stage_number + 1,
            title="Active Stage",
            planned_duration_days=10,
            is_active=True,
        )
        stage3 = Stage(
            direction_id=direction.id,
            stage_number=stage.stage_number + 2,
            title="Inactive Stage",
            planned_duration_days=14,
            is_active=False,
        )
        db_session.add_all([stage2, stage3])
        await db_session.commit()

        service = MentorDeadlineService(db_session)
        _, _, previews = await service.calculate_all_stage_deadlines(student.id)

        assert len(previews) == 2
        assert all(p.stage.is_active for p in previews)

    async def test_calculate_all_stage_deadlines_starts_from_current(
        self, db_session, student, direction, stage, student_progress
    ):
        """Test calculate deadlines starts from current stage."""
        from sputnik_offer_crm.models import Stage

        # Current stage is stage_number 1, create stage 2 and 3
        stage.planned_duration_days = 14
        await db_session.commit()

        stage2 = Stage(
            direction_id=direction.id,
            stage_number=stage.stage_number + 1,
            title="Next Stage",
            planned_duration_days=10,
            is_active=True,
        )
        stage3 = Stage(
            direction_id=direction.id,
            stage_number=stage.stage_number + 2,
            title="Future Stage",
            planned_duration_days=7,
            is_active=True,
        )
        db_session.add_all([stage2, stage3])
        await db_session.commit()

        service = MentorDeadlineService(db_session)
        _, _, previews = await service.calculate_all_stage_deadlines(student.id)

        # Should include current and all future stages
        assert len(previews) == 3
        assert previews[0].stage.id == stage.id
        assert previews[1].stage.id == stage2.id
        assert previews[2].stage.id == stage3.id

    async def test_calculate_all_stage_deadlines_student_not_found(self, db_session):
        """Test calculate deadlines for non-existent student."""
        service = MentorDeadlineService(db_session)

        with pytest.raises(DeadlineStudentNotFoundError):
            await service.calculate_all_stage_deadlines(999999)

    async def test_calculate_all_stage_deadlines_no_progress(self, db_session, student):
        """Test calculate deadlines for student without progress."""
        service = MentorDeadlineService(db_session)

        with pytest.raises(DeadlineStudentHasNoProgressError):
            await service.calculate_all_stage_deadlines(student.id)

    async def test_set_all_stage_deadlines_creates_new_records(
        self, db_session, student, direction, stage, student_progress
    ):
        """Test set all stage deadlines creates new StudentStageProgress records."""
        from sqlalchemy import select
        from sputnik_offer_crm.models import Stage

        # Create additional stages
        stage2 = Stage(
            direction_id=direction.id,
            stage_number=stage.stage_number + 1,
            title="Stage 2",
            is_active=True,
        )
        db_session.add(stage2)
        await db_session.commit()

        deadline1 = date.today() + timedelta(days=7)
        deadline2 = date.today() + timedelta(days=14)

        service = MentorDeadlineService(db_session)
        count = await service.set_all_stage_deadlines(
            student.id,
            [(stage.id, deadline1), (stage2.id, deadline2)]
        )

        assert count == 2

        # Verify records created
        result = await db_session.execute(
            select(StudentStageProgress).where(
                StudentStageProgress.student_id == student.id
            ).order_by(StudentStageProgress.stage_id)
        )
        records = list(result.scalars().all())

        assert len(records) == 2
        assert records[0].stage_id == stage.id
        assert records[0].planned_deadline == deadline1
        assert records[1].stage_id == stage2.id
        assert records[1].planned_deadline == deadline2

    async def test_set_all_stage_deadlines_updates_existing_records(
        self, db_session, student, direction, stage, student_progress, student_stage_progress
    ):
        """Test set all stage deadlines updates existing StudentStageProgress records."""
        old_deadline = date.today() + timedelta(days=3)
        student_stage_progress.planned_deadline = old_deadline
        await db_session.commit()

        new_deadline = date.today() + timedelta(days=14)

        service = MentorDeadlineService(db_session)
        count = await service.set_all_stage_deadlines(
            student.id,
            [(stage.id, new_deadline)]
        )

        assert count == 1

        # Verify deadline updated
        await db_session.refresh(student_stage_progress)
        assert student_stage_progress.planned_deadline == new_deadline

    async def test_set_all_stage_deadlines_student_not_found(self, db_session):
        """Test set all stage deadlines for non-existent student."""
        service = MentorDeadlineService(db_session)

        with pytest.raises(DeadlineStudentNotFoundError):
            await service.set_all_stage_deadlines(999999, [])

    async def test_set_all_stage_deadlines_no_progress(self, db_session, student):
        """Test set all stage deadlines for student without progress."""
        service = MentorDeadlineService(db_session)

        with pytest.raises(DeadlineStudentHasNoProgressError):
            await service.set_all_stage_deadlines(student.id, [])

    async def test_bulk_deadlines_visible_in_student_view(
        self, db_session, student, direction, stage, student_progress
    ):
        """Test that bulk deadlines are visible in student deadlines view."""
        from sputnik_offer_crm.models import Stage
        from sputnik_offer_crm.services import StudentService

        # Create additional stage
        stage2 = Stage(
            direction_id=direction.id,
            stage_number=stage.stage_number + 1,
            title="Stage 2",
            is_active=True,
        )
        db_session.add(stage2)
        await db_session.commit()

        deadline1 = date.today() + timedelta(days=7)
        deadline2 = date.today() + timedelta(days=14)

        # Set bulk deadlines
        deadline_service = MentorDeadlineService(db_session)
        await deadline_service.set_all_stage_deadlines(
            student.id,
            [(stage.id, deadline1), (stage2.id, deadline2)]
        )

        # Check they're visible in student deadlines
        student_service = StudentService(db_session)
        deadlines = await student_service.get_student_deadlines(student.telegram_id)

        # Should have both stage deadlines
        assert len(deadlines) == 2

        stage1_deadlines = [d for d in deadlines if d.title == f"Этап: {stage.title}"]
        assert len(stage1_deadlines) == 1
        assert stage1_deadlines[0].deadline_date == deadline1

        stage2_deadlines = [d for d in deadlines if d.title == f"Этап: {stage2.title}"]
        assert len(stage2_deadlines) == 1
        assert stage2_deadlines[0].deadline_date == deadline2
