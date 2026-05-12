"""Mentor progress management service."""

from datetime import date, datetime, timezone
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sputnik_offer_crm.models import (
    Stage,
    Student,
    StudentProgress,
    StudentStageProgress,
)


class NextStageInfo(NamedTuple):
    """Information about next stage transition."""

    current_stage: Stage
    next_stage: Stage
    student: Student


class MoveToNextStageError(Exception):
    """Base error for move to next stage operation."""


class StudentNotFoundError(MoveToNextStageError):
    """Student not found."""


class StudentHasNoProgressError(MoveToNextStageError):
    """Student has no progress record."""


class AlreadyOnFinalStageError(MoveToNextStageError):
    """Student is already on the final stage."""


class NextStageNotFoundError(MoveToNextStageError):
    """Next stage not found in direction."""


class MentorProgressService:
    """Service for mentor progress management operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_next_stage_info(self, student_id: int) -> NextStageInfo:
        """
        Get information about next stage for student.

        Args:
            student_id: student ID

        Returns:
            NextStageInfo with current and next stage

        Raises:
            StudentNotFoundError: if student not found
            StudentHasNoProgressError: if student has no progress
            AlreadyOnFinalStageError: if student is on final stage
            NextStageNotFoundError: if next stage not found
        """
        # Get student
        result = await self.session.execute(
            select(Student).where(Student.id == student_id)
        )
        student = result.scalar_one_or_none()

        if not student:
            raise StudentNotFoundError(f"Student {student_id} not found")

        # Get student progress
        result = await self.session.execute(
            select(StudentProgress).where(StudentProgress.student_id == student.id)
        )
        progress = result.scalar_one_or_none()

        if not progress:
            raise StudentHasNoProgressError(
                f"Student {student_id} has no progress record"
            )

        # Get current stage
        result = await self.session.execute(
            select(Stage).where(Stage.id == progress.current_stage_id)
        )
        current_stage = result.scalar_one()

        # Find next stage in the same direction
        result = await self.session.execute(
            select(Stage)
            .where(
                Stage.direction_id == progress.direction_id,
                Stage.stage_number == current_stage.stage_number + 1,
                Stage.is_active == True,  # noqa: E712
            )
        )
        next_stage = result.scalar_one_or_none()

        if not next_stage:
            # Check if there are any stages with higher number
            result = await self.session.execute(
                select(Stage)
                .where(
                    Stage.direction_id == progress.direction_id,
                    Stage.stage_number > current_stage.stage_number,
                    Stage.is_active == True,  # noqa: E712
                )
                .limit(1)
            )
            if result.scalar_one_or_none() is None:
                raise AlreadyOnFinalStageError(
                    f"Student {student_id} is already on final stage"
                )
            raise NextStageNotFoundError(
                f"Next stage not found for direction {progress.direction_id}"
            )

        return NextStageInfo(
            current_stage=current_stage,
            next_stage=next_stage,
            student=student,
        )

    async def move_to_next_stage(self, student_id: int) -> Stage:
        """
        Move student to next stage.

        This operation:
        1. Updates StudentProgress.current_stage_id to next stage
        2. Marks current StudentStageProgress as done (if exists)
        3. Creates or updates StudentStageProgress for next stage as active

        Args:
            student_id: student ID

        Returns:
            Next stage that student was moved to

        Raises:
            StudentNotFoundError: if student not found
            StudentHasNoProgressError: if student has no progress
            AlreadyOnFinalStageError: if student is on final stage
            NextStageNotFoundError: if next stage not found
        """
        # Get next stage info (validates everything)
        info = await self.get_next_stage_info(student_id)

        today = date.today()

        # 1. Update StudentProgress to point to next stage
        result = await self.session.execute(
            select(StudentProgress).where(StudentProgress.student_id == student_id)
        )
        progress = result.scalar_one()
        progress.current_stage_id = info.next_stage.id

        # 2. Mark current stage progress as done (if exists)
        result = await self.session.execute(
            select(StudentStageProgress).where(
                StudentStageProgress.student_id == student_id,
                StudentStageProgress.stage_id == info.current_stage.id,
            )
        )
        current_stage_progress = result.scalar_one_or_none()

        if current_stage_progress:
            current_stage_progress.status = "done"
            current_stage_progress.completed_at = today
            current_stage_progress.updated_at = datetime.now(timezone.utc)

        # 3. Create or update next stage progress as active
        result = await self.session.execute(
            select(StudentStageProgress).where(
                StudentStageProgress.student_id == student_id,
                StudentStageProgress.stage_id == info.next_stage.id,
            )
        )
        next_stage_progress = result.scalar_one_or_none()

        if next_stage_progress:
            # Update existing record
            next_stage_progress.status = "active"
            if not next_stage_progress.started_at:
                next_stage_progress.started_at = today
            next_stage_progress.updated_at = datetime.now(timezone.utc)
        else:
            # Create new record
            next_stage_progress = StudentStageProgress(
                student_id=student_id,
                stage_id=info.next_stage.id,
                status="active",
                started_at=today,
            )
            self.session.add(next_stage_progress)

        await self.session.commit()

        return info.next_stage
