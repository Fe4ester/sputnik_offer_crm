"""Tests for MentorOfferCompletionService."""

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from sputnik_offer_crm.models import Student
from sputnik_offer_crm.services.mentor_offer_completion import (
    MentorOfferCompletionService,
    OfferCompletionStudentNotFoundError,
    StudentAlreadyCompletedError,
    StudentInactiveError,
)


@pytest.fixture
def service(db_session: AsyncSession) -> MentorOfferCompletionService:
    """Create service instance."""
    return MentorOfferCompletionService(db_session)


@pytest.fixture
async def active_student(db_session: AsyncSession) -> Student:
    """Create active student without offer."""
    student = Student(
        telegram_id=123456789,
        first_name="Test",
        last_name="Student",
        username="teststudent",
        timezone="Europe/Moscow",
        is_active=True,
    )
    db_session.add(student)
    await db_session.commit()
    await db_session.refresh(student)
    return student


@pytest.fixture
async def inactive_student(db_session: AsyncSession) -> Student:
    """Create inactive student."""
    student = Student(
        telegram_id=987654321,
        first_name="Inactive",
        last_name="Student",
        username="inactivestudent",
        timezone="Europe/Moscow",
        is_active=False,
    )
    db_session.add(student)
    await db_session.commit()
    await db_session.refresh(student)
    return student


@pytest.fixture
async def completed_student(db_session: AsyncSession) -> Student:
    """Create student already completed with offer."""
    student = Student(
        telegram_id=111222333,
        first_name="Completed",
        last_name="Student",
        username="completedstudent",
        timezone="Europe/Moscow",
        is_active=True,
        offer_company="Test Company",
        offer_position="Test Position",
        offer_received_at=datetime.now(timezone.utc),
    )
    db_session.add(student)
    await db_session.commit()
    await db_session.refresh(student)
    return student


@pytest.mark.asyncio
async def test_complete_with_offer_success(
    service: MentorOfferCompletionService,
    active_student: Student,
) -> None:
    """Test successful offer completion."""
    company = "Google"
    position = "Senior Software Engineer"

    result = await service.complete_with_offer(
        active_student.id, company, position
    )

    assert result.id == active_student.id
    assert result.offer_company == company
    assert result.offer_position == position
    assert result.offer_received_at is not None
    assert result.is_active is True


@pytest.mark.asyncio
async def test_complete_with_offer_strips_whitespace(
    service: MentorOfferCompletionService,
    active_student: Student,
) -> None:
    """Test that company and position are stripped."""
    company = "  Google  "
    position = "  Senior Software Engineer  "

    result = await service.complete_with_offer(
        active_student.id, company, position
    )

    assert result.offer_company == "Google"
    assert result.offer_position == "Senior Software Engineer"


@pytest.mark.asyncio
async def test_complete_with_offer_student_not_found(
    service: MentorOfferCompletionService,
) -> None:
    """Test error when student not found."""
    with pytest.raises(OfferCompletionStudentNotFoundError):
        await service.complete_with_offer(99999, "Company", "Position")


@pytest.mark.asyncio
async def test_complete_with_offer_student_inactive(
    service: MentorOfferCompletionService,
    inactive_student: Student,
) -> None:
    """Test error when student is inactive."""
    with pytest.raises(StudentInactiveError):
        await service.complete_with_offer(
            inactive_student.id, "Company", "Position"
        )


@pytest.mark.asyncio
async def test_complete_with_offer_already_completed(
    service: MentorOfferCompletionService,
    completed_student: Student,
) -> None:
    """Test error when student already completed."""
    with pytest.raises(StudentAlreadyCompletedError):
        await service.complete_with_offer(
            completed_student.id, "New Company", "New Position"
        )


@pytest.mark.asyncio
async def test_complete_with_offer_preserves_active_status(
    service: MentorOfferCompletionService,
    active_student: Student,
) -> None:
    """Test that completing with offer keeps student active."""
    result = await service.complete_with_offer(
        active_student.id, "Company", "Position"
    )

    assert result.is_active is True


@pytest.mark.asyncio
async def test_complete_with_offer_sets_timestamp(
    service: MentorOfferCompletionService,
    active_student: Student,
) -> None:
    """Test that offer_received_at is set to current time."""
    before = datetime.now(timezone.utc)

    result = await service.complete_with_offer(
        active_student.id, "Company", "Position"
    )

    after = datetime.now(timezone.utc)

    assert result.offer_received_at is not None
    assert before <= result.offer_received_at <= after
