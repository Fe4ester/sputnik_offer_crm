"""Service for student timezone management."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sputnik_offer_crm.models import Student


class StudentTimezoneError(Exception):
    """Base exception for student timezone errors."""


class StudentNotFoundError(StudentTimezoneError):
    """Student not found."""


class StudentTimezoneService:
    """Service for student timezone management."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_student_timezone(self, telegram_id: int) -> tuple[Student, str]:
        """
        Get student's current timezone.

        Args:
            telegram_id: student telegram ID

        Returns:
            Tuple of (student, timezone)

        Raises:
            StudentNotFoundError: if student not found
        """
        result = await self.session.execute(
            select(Student).where(Student.telegram_id == telegram_id)
        )
        student = result.scalar_one_or_none()

        if not student:
            raise StudentNotFoundError(f"Student with telegram_id {telegram_id} not found")

        return student, student.timezone

    async def update_student_timezone(
        self,
        telegram_id: int,
        new_timezone: str,
    ) -> tuple[Student, str, str]:
        """
        Update student's timezone.

        Args:
            telegram_id: student telegram ID
            new_timezone: new timezone string

        Returns:
            Tuple of (student, old_timezone, new_timezone)

        Raises:
            StudentNotFoundError: if student not found
        """
        result = await self.session.execute(
            select(Student).where(Student.telegram_id == telegram_id)
        )
        student = result.scalar_one_or_none()

        if not student:
            raise StudentNotFoundError(f"Student with telegram_id {telegram_id} not found")

        old_timezone = student.timezone
        student.timezone = new_timezone.strip()

        await self.session.flush()
        await self.session.refresh(student)

        return student, old_timezone, new_timezone
