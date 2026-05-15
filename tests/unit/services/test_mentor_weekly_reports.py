"""Tests for MentorWeeklyReportsService."""

from datetime import date, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from sputnik_offer_crm.models import Student, StudentStatus, WeeklyReport
from sputnik_offer_crm.services.mentor_weekly_reports import (
    MentorWeeklyReportsService,
    ReportNotFoundError,
    StudentNotFoundError,
)


@pytest.fixture
def service(db_session: AsyncSession) -> MentorWeeklyReportsService:
    """Create service instance."""
    return MentorWeeklyReportsService(db_session)


@pytest.fixture
async def student(db_session: AsyncSession) -> Student:
    """Create test student."""
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
async def student2(db_session: AsyncSession) -> Student:
    """Create second test student."""
    student = Student(
        telegram_id=987654321,
        first_name="Another",
        last_name="Student",
        username="anotherstudent",
        timezone="Europe/Moscow",
    )
    student.set_status(StudentStatus.ACTIVE)
    db_session.add(student)
    await db_session.commit()
    await db_session.refresh(student)
    return student


@pytest.mark.asyncio
async def test_get_student_reports_empty(
    service: MentorWeeklyReportsService,
    student: Student,
) -> None:
    """Test getting reports when student has none."""
    reports = await service.get_student_reports(student.id)
    assert reports == []


@pytest.mark.asyncio
async def test_get_student_reports_multiple(
    service: MentorWeeklyReportsService,
    student: Student,
    db_session: AsyncSession,
) -> None:
    """Test getting multiple reports."""
    # Create reports
    report1 = WeeklyReport(
        student_id=student.id,
        week_start_date=date.today() - timedelta(days=14),
        answer_what_did="Week 1 work",
    )
    report2 = WeeklyReport(
        student_id=student.id,
        week_start_date=date.today() - timedelta(days=7),
        answer_what_did="Week 2 work",
        answer_problems_unsolved="Need help",
    )
    report3 = WeeklyReport(
        student_id=student.id,
        week_start_date=date.today(),
        answer_what_did="Week 3 work",
    )
    db_session.add_all([report1, report2, report3])
    await db_session.commit()

    reports = await service.get_student_reports(student.id)

    assert len(reports) == 3
    # Ordered by week_start_date desc
    assert reports[0].week_start_date == date.today()
    assert reports[0].has_problems_unsolved is False
    assert reports[1].week_start_date == date.today() - timedelta(days=7)
    assert reports[1].has_problems_unsolved is True
    assert reports[2].week_start_date == date.today() - timedelta(days=14)
    assert "Test Student" in reports[0].student_name


@pytest.mark.asyncio
async def test_get_student_reports_limit(
    service: MentorWeeklyReportsService,
    student: Student,
    db_session: AsyncSession,
) -> None:
    """Test limit parameter."""
    # Create 5 reports
    for i in range(5):
        report = WeeklyReport(
            student_id=student.id,
            week_start_date=date.today() - timedelta(days=i * 7),
            answer_what_did=f"Week {i} work",
        )
        db_session.add(report)
    await db_session.commit()

    reports = await service.get_student_reports(student.id, limit=3)

    assert len(reports) == 3


@pytest.mark.asyncio
async def test_get_student_reports_student_not_found(
    service: MentorWeeklyReportsService,
) -> None:
    """Test error when student not found."""
    with pytest.raises(StudentNotFoundError):
        await service.get_student_reports(99999)


@pytest.mark.asyncio
async def test_get_report_detail_success(
    service: MentorWeeklyReportsService,
    student: Student,
    db_session: AsyncSession,
) -> None:
    """Test getting full report details."""
    # Create report
    report = WeeklyReport(
        student_id=student.id,
        week_start_date=date.today(),
        answer_what_did="Completed tasks",
        answer_problems_solved="Fixed bug",
        answer_problems_unsolved="Need help with deployment",
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)

    detail = await service.get_report_detail(report.id)

    assert detail.id == report.id
    assert detail.week_start_date == date.today()
    assert "Test Student" in detail.student_name
    assert detail.answer_what_did == "Completed tasks"
    assert detail.answer_problems_solved == "Fixed bug"
    assert detail.answer_problems_unsolved == "Need help with deployment"


@pytest.mark.asyncio
async def test_get_report_detail_not_found(
    service: MentorWeeklyReportsService,
) -> None:
    """Test error when report not found."""
    with pytest.raises(ReportNotFoundError):
        await service.get_report_detail(99999)


@pytest.mark.asyncio
async def test_get_recent_reports_empty(
    service: MentorWeeklyReportsService,
) -> None:
    """Test getting recent reports when none exist."""
    reports = await service.get_recent_reports()
    assert reports == []


@pytest.mark.asyncio
async def test_get_recent_reports_multiple_students(
    service: MentorWeeklyReportsService,
    student: Student,
    student2: Student,
    db_session: AsyncSession,
) -> None:
    """Test getting recent reports across multiple students."""
    # Create reports for both students
    report1 = WeeklyReport(
        student_id=student.id,
        week_start_date=date.today() - timedelta(days=7),
        answer_what_did="Student 1 work",
    )
    report2 = WeeklyReport(
        student_id=student2.id,
        week_start_date=date.today(),
        answer_what_did="Student 2 work",
    )
    report3 = WeeklyReport(
        student_id=student.id,
        week_start_date=date.today() - timedelta(days=14),
        answer_what_did="Student 1 old work",
    )
    db_session.add_all([report1, report2, report3])
    await db_session.commit()

    reports = await service.get_recent_reports()

    assert len(reports) == 3
    # Ordered by week_start_date desc
    assert reports[0].week_start_date == date.today()
    assert "Another Student" in reports[0].student_name
    assert reports[1].week_start_date == date.today() - timedelta(days=7)
    assert "Test Student" in reports[1].student_name


@pytest.mark.asyncio
async def test_get_recent_reports_limit(
    service: MentorWeeklyReportsService,
    student: Student,
    db_session: AsyncSession,
) -> None:
    """Test limit parameter for recent reports."""
    # Create 5 reports
    for i in range(5):
        report = WeeklyReport(
            student_id=student.id,
            week_start_date=date.today() - timedelta(days=i * 7),
            answer_what_did=f"Week {i} work",
        )
        db_session.add(report)
    await db_session.commit()

    reports = await service.get_recent_reports(limit=3)

    assert len(reports) == 3
