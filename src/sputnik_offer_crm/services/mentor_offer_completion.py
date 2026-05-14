"""Mentor offer completion service."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sputnik_offer_crm.models import Student


class OfferCompletionError(Exception):
    """Base error for offer completion operations."""


class OfferCompletionStudentNotFoundError(OfferCompletionError):
    """Student not found."""


class StudentAlreadyCompletedError(OfferCompletionError):
    """Student already completed with offer."""


class StudentInactiveError(OfferCompletionError):
    """Student is inactive."""


class MentorOfferCompletionService:
    """Service for mentor offer completion operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def complete_with_offer(
        self, student_id: int, company: str, position: str
    ) -> Student:
        """
        Complete student with offer.

        This operation:
        1. Sets offer_company, offer_position, offer_received_at
        2. Keeps student.is_active = True (student completed successfully)
        3. Preserves all historical data

        Args:
            student_id: student ID
            company: company name
            position: position title

        Returns:
            Updated student

        Raises:
            OfferCompletionStudentNotFoundError: if student not found
            StudentAlreadyCompletedError: if student already has offer data
            StudentInactiveError: if student is inactive
        """
        result = await self.session.execute(
            select(Student).where(Student.id == student_id)
        )
        student = result.scalar_one_or_none()

        if not student:
            raise OfferCompletionStudentNotFoundError(f"Student {student_id} not found")

        if student.is_dropped():
            raise StudentInactiveError(
                f"Student {student_id} is inactive (dropped out)"
            )

        if student.offer_received_at is not None:
            raise StudentAlreadyCompletedError(
                f"Student {student_id} already completed with offer"
            )

        student.offer_company = company.strip()
        student.offer_position = position.strip()
        student.offer_received_at = datetime.now(timezone.utc)

        await self.session.commit()

        return student
