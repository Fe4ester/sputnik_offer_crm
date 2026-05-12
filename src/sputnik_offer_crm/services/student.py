"""Student service."""

from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sputnik_offer_crm.models import Direction, DirectionStage, Student, StudentProgress


class StudentProgressInfo(NamedTuple):
    """Student progress information."""

    student: Student
    direction: Direction
    current_stage: DirectionStage
    progress: StudentProgress


class StudentService:
    """Service for student operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_student_progress(self, telegram_id: int) -> StudentProgressInfo | None:
        """
        Get student progress information.

        Returns:
            StudentProgressInfo or None if student not found
        """
        # Get student
        result = await self.session.execute(
            select(Student).where(Student.telegram_id == telegram_id)
        )
        student = result.scalar_one_or_none()

        if not student:
            return None

        # Get student progress
        result = await self.session.execute(
            select(StudentProgress).where(StudentProgress.student_id == student.id)
        )
        progress = result.scalar_one_or_none()

        if not progress:
            return None

        # Get direction
        result = await self.session.execute(
            select(Direction).where(Direction.id == progress.direction_id)
        )
        direction = result.scalar_one()

        # Get current stage
        result = await self.session.execute(
            select(DirectionStage).where(DirectionStage.id == progress.current_stage_id)
        )
        current_stage = result.scalar_one()

        return StudentProgressInfo(
            student=student,
            direction=direction,
            current_stage=current_stage,
            progress=progress,
        )

    async def get_student_deadlines(self, telegram_id: int) -> list:
        """
        Get student deadlines.

        Currently returns empty list as deadline functionality is not yet implemented.
        This is a placeholder for future deadline management.

        Returns:
            List of deadlines (empty for now)
        """
        # Placeholder: deadline functionality not yet implemented
        # When implemented, this will query deadline-related tables
        return []
