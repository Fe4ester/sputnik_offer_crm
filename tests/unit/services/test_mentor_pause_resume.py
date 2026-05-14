"""Tests for MentorPauseResumeService."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from sputnik_offer_crm.models import Student
from sputnik_offer_crm.services.mentor_pause_resume import (
    MentorPauseResumeService,
    PauseResumeStudentNotFoundError,
    StudentInactiveError,
    StudentAlreadyPausedError,
    StudentNotPausedError,
)


@pytest.fixture
def service(db_session: AsyncSession) -> MentorPauseResumeService:
    """Create service instance."""
    return MentorPauseResumeService(db_session)


@pytest.fixture
async def active_student(db_session: AsyncSession) -> Student:
    """Create active student not on pause."""
    from sputnik_offer_crm.models import StudentStatus
    student = Student(
        telegram_id=123456789,
        first_name="Test",
        last_name="Student",
        username="teststudent",
        timezone="Europe/Moscow",
    )
    student.set_status(StudentStatus.ACTIVE)
    db_session.add(student)
    await db_session.commit()
    await db_session.refresh(student)
    return student


@pytest.fixture
async def paused_student(db_session: AsyncSession) -> Student:
    """Create paused student."""
    from sputnik_offer_crm.models import StudentStatus
    student = Student(
        telegram_id=987654321,
        first_name="Paused",
        last_name="Student",
        username="pausedstudent",
        timezone="Europe/Moscow",
    )
    student.set_status(StudentStatus.PAUSED)
    db_session.add(student)
    await db_session.commit()
    await db_session.refresh(student)
    return student


@pytest.fixture
async def inactive_student(db_session: AsyncSession) -> Student:
    """Create inactive (dropped out) student."""
    from sputnik_offer_crm.models import StudentStatus
    student = Student(
        telegram_id=111222333,
        first_name="Inactive",
        last_name="Student",
        username="inactivestudent",
        timezone="Europe/Moscow",
    )
    student.set_status(StudentStatus.DROPPED)
    db_session.add(student)
    await db_session.commit()
    await db_session.refresh(student)
    return student


@pytest.mark.asyncio
async def test_pause_student_success(
    service: MentorPauseResumeService,
    active_student: Student,
) -> None:
    """Test successful student pause."""
    result = await service.pause_student(active_student.id)

    assert result.id == active_student.id
    assert result.is_paused is True
    assert result.is_active is True


@pytest.mark.asyncio
async def test_pause_student_not_found(
    service: MentorPauseResumeService,
) -> None:
    """Test error when student not found."""
    with pytest.raises(PauseResumeStudentNotFoundError):
        await service.pause_student(99999)


@pytest.mark.asyncio
async def test_pause_student_inactive(
    service: MentorPauseResumeService,
    inactive_student: Student,
) -> None:
    """Test error when trying to pause inactive student."""
    with pytest.raises(StudentInactiveError):
        await service.pause_student(inactive_student.id)


@pytest.mark.asyncio
async def test_pause_student_already_paused(
    service: MentorPauseResumeService,
    paused_student: Student,
) -> None:
    """Test error when student already paused."""
    with pytest.raises(StudentAlreadyPausedError):
        await service.pause_student(paused_student.id)


@pytest.mark.asyncio
async def test_pause_preserves_active_status(
    service: MentorPauseResumeService,
    active_student: Student,
) -> None:
    """Test that pause keeps student active (not dropped out)."""
    result = await service.pause_student(active_student.id)

    assert result.is_active is True
    assert result.is_paused is True


@pytest.mark.asyncio
async def test_resume_student_success(
    service: MentorPauseResumeService,
    paused_student: Student,
) -> None:
    """Test successful student resume."""
    result = await service.resume_student(paused_student.id)

    assert result.id == paused_student.id
    assert result.is_paused is False
    assert result.is_active is True


@pytest.mark.asyncio
async def test_resume_student_not_found(
    service: MentorPauseResumeService,
) -> None:
    """Test error when student not found."""
    with pytest.raises(PauseResumeStudentNotFoundError):
        await service.resume_student(99999)


@pytest.mark.asyncio
async def test_resume_student_inactive(
    service: MentorPauseResumeService,
    inactive_student: Student,
) -> None:
    """Test error when trying to resume inactive student."""
    with pytest.raises(StudentInactiveError):
        await service.resume_student(inactive_student.id)


@pytest.mark.asyncio
async def test_resume_student_not_paused(
    service: MentorPauseResumeService,
    active_student: Student,
) -> None:
    """Test error when student not paused."""
    with pytest.raises(StudentNotPausedError):
        await service.resume_student(active_student.id)


@pytest.mark.asyncio
async def test_pause_resume_cycle(
    service: MentorPauseResumeService,
    active_student: Student,
) -> None:
    """Test full pause/resume cycle."""
    # Pause
    paused = await service.pause_student(active_student.id)
    assert paused.is_paused is True
    assert paused.is_active is True

    # Resume
    resumed = await service.resume_student(active_student.id)
    assert resumed.is_paused is False
    assert resumed.is_active is True


@pytest.mark.asyncio
async def test_pause_preserves_student_data(
    service: MentorPauseResumeService,
    active_student: Student,
) -> None:
    """Test that pause preserves all student data."""
    original_name = active_student.first_name
    original_telegram_id = active_student.telegram_id

    result = await service.pause_student(active_student.id)

    assert result.first_name == original_name
    assert result.telegram_id == original_telegram_id
