"""Tests for StudentTimezoneService."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from sputnik_offer_crm.models import Student
from sputnik_offer_crm.services.student_timezone import (
    StudentNotFoundError,
    StudentTimezoneService,
)


@pytest.fixture
def service(db_session: AsyncSession) -> StudentTimezoneService:
    """Create service instance."""
    return StudentTimezoneService(db_session)


@pytest.fixture
async def student(db_session: AsyncSession) -> Student:
    """Create test student."""
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


@pytest.mark.asyncio
async def test_get_student_timezone(
    service: StudentTimezoneService,
    student: Student,
) -> None:
    """Test getting student timezone."""
    result_student, timezone = await service.get_student_timezone(student.telegram_id)

    assert result_student.id == student.id
    assert timezone == "Europe/Moscow"


@pytest.mark.asyncio
async def test_get_student_timezone_not_found(
    service: StudentTimezoneService,
) -> None:
    """Test getting timezone for non-existent student."""
    with pytest.raises(StudentNotFoundError):
        await service.get_student_timezone(999999999)


@pytest.mark.asyncio
async def test_update_student_timezone(
    service: StudentTimezoneService,
    student: Student,
    db_session: AsyncSession,
) -> None:
    """Test updating student timezone."""
    result_student, old_tz, new_tz = await service.update_student_timezone(
        student.telegram_id,
        "Asia/Tokyo",
    )
    await db_session.commit()

    assert result_student.id == student.id
    assert old_tz == "Europe/Moscow"
    assert new_tz == "Asia/Tokyo"
    assert result_student.timezone == "Asia/Tokyo"


@pytest.mark.asyncio
async def test_update_student_timezone_strips_whitespace(
    service: StudentTimezoneService,
    student: Student,
    db_session: AsyncSession,
) -> None:
    """Test that timezone is stripped of whitespace."""
    result_student, old_tz, new_tz = await service.update_student_timezone(
        student.telegram_id,
        "  Asia/Dubai  ",
    )
    await db_session.commit()

    assert result_student.timezone == "Asia/Dubai"


@pytest.mark.asyncio
async def test_update_student_timezone_not_found(
    service: StudentTimezoneService,
) -> None:
    """Test updating timezone for non-existent student."""
    with pytest.raises(StudentNotFoundError):
        await service.update_student_timezone(999999999, "UTC")


@pytest.mark.asyncio
async def test_update_student_timezone_same_value(
    service: StudentTimezoneService,
    student: Student,
    db_session: AsyncSession,
) -> None:
    """Test updating timezone to the same value."""
    result_student, old_tz, new_tz = await service.update_student_timezone(
        student.telegram_id,
        "Europe/Moscow",
    )
    await db_session.commit()

    assert old_tz == "Europe/Moscow"
    assert new_tz == "Europe/Moscow"
    assert result_student.timezone == "Europe/Moscow"


@pytest.mark.asyncio
async def test_update_student_timezone_multiple_times(
    service: StudentTimezoneService,
    student: Student,
    db_session: AsyncSession,
) -> None:
    """Test updating timezone multiple times."""
    # First update
    _, old_tz1, new_tz1 = await service.update_student_timezone(
        student.telegram_id,
        "Asia/Tokyo",
    )
    await db_session.commit()

    assert old_tz1 == "Europe/Moscow"
    assert new_tz1 == "Asia/Tokyo"

    # Second update
    _, old_tz2, new_tz2 = await service.update_student_timezone(
        student.telegram_id,
        "America/New_York",
    )
    await db_session.commit()

    assert old_tz2 == "Asia/Tokyo"
    assert new_tz2 == "America/New_York"

    # Verify final state
    result_student, final_tz = await service.get_student_timezone(student.telegram_id)
    assert final_tz == "America/New_York"
