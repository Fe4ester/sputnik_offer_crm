"""Mentor pause/resume service."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sputnik_offer_crm.models import Student, StudentStatus


class PauseResumeError(Exception):
    """Base error for pause/resume operations."""


class PauseResumeStudentNotFoundError(PauseResumeError):
    """Student not found."""


class StudentAlreadyPausedError(PauseResumeError):
    """Student is already paused."""


class StudentNotPausedError(PauseResumeError):
    """Student is not paused."""


class StudentInactiveError(PauseResumeError):
    """Student is inactive (dropped out)."""


class MentorPauseResumeService:
    """Service for mentor pause/resume operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def pause_student(self, student_id: int) -> Student:
        """
        Pause student.

        This operation:
        1. Sets student.status = 'paused'
        2. Preserves all historical data (progress, reports, tasks, deadlines)
        3. Blocks active student-side actions (weekly reports, etc.)

        Args:
            student_id: student ID

        Returns:
            Updated student

        Raises:
            PauseResumeStudentNotFoundError: if student not found
            StudentInactiveError: if student is inactive (dropped out)
            StudentAlreadyPausedError: if student is already paused
        """
        result = await self.session.execute(
            select(Student).where(Student.id == student_id)
        )
        student = result.scalar_one_or_none()

        if not student:
            raise PauseResumeStudentNotFoundError(f"Student {student_id} not found")

        if student.is_dropped():
            raise StudentInactiveError(
                f"Student {student_id} is inactive (dropped out)"
            )

        if student.is_on_pause():
            raise StudentAlreadyPausedError(f"Student {student_id} is already paused")

        student.set_status(StudentStatus.PAUSED)

        await self.session.commit()

        return student

    async def resume_student(self, student_id: int) -> Student:
        """
        Resume student from pause.

        This operation:
        1. Sets student.status = 'active'
        2. Restores active student-side actions
        3. Preserves all historical data

        Args:
            student_id: student ID

        Returns:
            Updated student

        Raises:
            PauseResumeStudentNotFoundError: if student not found
            StudentInactiveError: if student is inactive (dropped out)
            StudentNotPausedError: if student is not paused
        """
        result = await self.session.execute(
            select(Student).where(Student.id == student_id)
        )
        student = result.scalar_one_or_none()

        if not student:
            raise PauseResumeStudentNotFoundError(f"Student {student_id} not found")

        if student.is_dropped():
            raise StudentInactiveError(
                f"Student {student_id} is inactive (dropped out)"
            )

        if not student.is_on_pause():
            raise StudentNotPausedError(f"Student {student_id} is not paused")

        student.set_status(StudentStatus.ACTIVE)

        await self.session.commit()

        return student
