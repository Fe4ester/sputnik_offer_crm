"""Mentor deadline management service."""

from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sputnik_offer_crm.models import (
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
