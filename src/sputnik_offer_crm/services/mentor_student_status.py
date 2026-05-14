"""Mentor student status management service."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sputnik_offer_crm.models import Student


class StudentStatusManagementError(Exception):
    """Base error for student status management operations."""


class StudentNotFoundError(StudentStatusManagementError):
    """Student not found."""


class StudentAlreadyInactiveError(StudentStatusManagementError):
    """Student is already inactive."""


class MentorStudentStatusService:
    """Service for mentor student status management operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def dropout_student(self, student_id: int) -> Student:
        """
        Mark student as dropped (inactive).

        This operation:
        1. Sets student.is_active = False
        2. Preserves all historical data (progress, reports, tasks, deadlines)

        Args:
            student_id: student ID

        Returns:
            Updated student

        Raises:
            StudentNotFoundError: if student not found
            StudentAlreadyInactiveError: if student is already inactive
        """
        # Get student
        result = await self.session.execute(
            select(Student).where(Student.id == student_id)
        )
        student = result.scalar_one_or_none()

        if not student:
            raise StudentNotFoundError(f"Student {student_id} not found")

        if not student.is_active:
            raise StudentAlreadyInactiveError(
                f"Student {student_id} is already inactive"
            )

        # Mark as inactive (dropped)
        student.is_active = False

        await self.session.commit()

        return student
