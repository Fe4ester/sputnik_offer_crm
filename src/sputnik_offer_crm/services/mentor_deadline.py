"""Mentor deadline management service."""

from datetime import date, datetime, timedelta, timezone
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sputnik_offer_crm.models import (
    Direction,
    Stage,
    Student,
    StudentProgress,
    StudentStageProgress,
)


class DeadlineManagementError(Exception):
    """Base error for deadline management operations."""


class StudentNotFoundError(DeadlineManagementError):
    """Student not found."""


class StudentHasNoProgressError(DeadlineManagementError):
    """Student has no progress record."""


class InvalidDeadlineDateError(DeadlineManagementError):
    """Invalid deadline date."""


class NoStagesFoundError(DeadlineManagementError):
    """No stages found for direction."""


class StageDeadlinePreview(NamedTuple):
    """Preview of stage with calculated deadline."""

    stage: Stage
    calculated_deadline: date


class MentorDeadlineService:
    """Service for mentor deadline management operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_current_stage_deadline(
        self, student_id: int
    ) -> tuple[Stage, date | None]:
        """
        Get current stage and its deadline for student.

        Args:
            student_id: student ID

        Returns:
            Tuple of (current_stage, deadline_date or None)

        Raises:
            StudentNotFoundError: if student not found
            StudentHasNoProgressError: if student has no progress
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

        # Get current stage progress (if exists)
        result = await self.session.execute(
            select(StudentStageProgress).where(
                StudentStageProgress.student_id == student_id,
                StudentStageProgress.stage_id == current_stage.id,
            )
        )
        stage_progress = result.scalar_one_or_none()

        deadline = stage_progress.planned_deadline if stage_progress else None

        return current_stage, deadline

    async def set_current_stage_deadline(
        self, student_id: int, deadline_date: date
    ) -> Stage:
        """
        Set deadline for student's current stage.

        Args:
            student_id: student ID
            deadline_date: new deadline date

        Returns:
            Current stage

        Raises:
            StudentNotFoundError: if student not found
            StudentHasNoProgressError: if student has no progress
            InvalidDeadlineDateError: if deadline date is invalid
        """
        # Validate deadline date
        if deadline_date < date.today():
            raise InvalidDeadlineDateError(
                f"Deadline date {deadline_date} is in the past"
            )

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

        # Get or create current stage progress
        result = await self.session.execute(
            select(StudentStageProgress).where(
                StudentStageProgress.student_id == student_id,
                StudentStageProgress.stage_id == current_stage.id,
            )
        )
        stage_progress = result.scalar_one_or_none()

        if stage_progress:
            # Update existing record
            stage_progress.planned_deadline = deadline_date
            stage_progress.updated_at = datetime.now(timezone.utc)
        else:
            # Create new record
            stage_progress = StudentStageProgress(
                student_id=student_id,
                stage_id=current_stage.id,
                status="active",
                started_at=date.today(),
                planned_deadline=deadline_date,
            )
            self.session.add(stage_progress)

        await self.session.commit()

        return current_stage

    async def calculate_all_stage_deadlines(
        self, student_id: int, default_duration_days: int = 14
    ) -> tuple[Student, Direction, list[StageDeadlinePreview]]:
        """
        Calculate deadlines for all remaining stages starting from current.

        Args:
            student_id: student ID
            default_duration_days: default duration for stages without planned_duration_days

        Returns:
            Tuple of (student, direction, list of StageDeadlinePreview)

        Raises:
            StudentNotFoundError: if student not found
            StudentHasNoProgressError: if student has no progress
            NoStagesFoundError: if no stages found
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

        # Get direction
        result = await self.session.execute(
            select(Direction).where(Direction.id == progress.direction_id)
        )
        direction = result.scalar_one()

        # Get current stage
        result = await self.session.execute(
            select(Stage).where(Stage.id == progress.current_stage_id)
        )
        current_stage = result.scalar_one()

        # Get all active stages in direction starting from current
        result = await self.session.execute(
            select(Stage)
            .where(
                Stage.direction_id == progress.direction_id,
                Stage.stage_number >= current_stage.stage_number,
                Stage.is_active == True,  # noqa: E712
            )
            .order_by(Stage.stage_number)
        )
        stages = list(result.scalars().all())

        if not stages:
            raise NoStagesFoundError(
                f"No stages found for direction {progress.direction_id}"
            )

        # Calculate deadlines
        previews: list[StageDeadlinePreview] = []
        current_date = date.today()

        for stage in stages:
            # Use planned_duration_days if available, otherwise use default
            duration = stage.planned_duration_days or default_duration_days
            deadline = current_date + timedelta(days=duration)

            previews.append(
                StageDeadlinePreview(
                    stage=stage,
                    calculated_deadline=deadline,
                )
            )

            # Next stage starts after current deadline
            current_date = deadline

        return student, direction, previews

    async def set_all_stage_deadlines(
        self, student_id: int, stage_deadlines: list[tuple[int, date]]
    ) -> int:
        """
        Set deadlines for multiple stages.

        Args:
            student_id: student ID
            stage_deadlines: list of (stage_id, deadline_date) tuples

        Returns:
            Number of deadlines set

        Raises:
            StudentNotFoundError: if student not found
            StudentHasNoProgressError: if student has no progress
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

        count = 0

        for stage_id, deadline_date in stage_deadlines:
            # Get or create stage progress
            result = await self.session.execute(
                select(StudentStageProgress).where(
                    StudentStageProgress.student_id == student_id,
                    StudentStageProgress.stage_id == stage_id,
                )
            )
            stage_progress = result.scalar_one_or_none()

            if stage_progress:
                # Update existing record
                stage_progress.planned_deadline = deadline_date
                stage_progress.updated_at = datetime.now(timezone.utc)
            else:
                # Create new record
                stage_progress = StudentStageProgress(
                    student_id=student_id,
                    stage_id=stage_id,
                    status="not_started",
                    planned_deadline=deadline_date,
                )
                self.session.add(stage_progress)

            count += 1

        await self.session.commit()

        return count
