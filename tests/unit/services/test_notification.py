"""Tests for NotificationService."""

from datetime import date, datetime, timedelta

import pytest
import pytz
from sqlalchemy.ext.asyncio import AsyncSession

from sputnik_offer_crm.models import (
    Direction,
    NotificationLog,
    Stage,
    Student,
    StudentProgress,
    StudentStageProgress,
    StudentTask,
    WeeklyReport,
)
from sputnik_offer_crm.models.student_task import TaskStatus
from sputnik_offer_crm.services.notification import NotificationService


@pytest.fixture
def service(db_session: AsyncSession) -> NotificationService:
    """Create service instance."""
    return NotificationService(db_session)


@pytest.fixture
async def direction(db_session: AsyncSession) -> Direction:
    """Create test direction."""
    direction = Direction(code="test", name="Test Direction", is_active=True)
    db_session.add(direction)
    await db_session.commit()
    await db_session.refresh(direction)
    return direction


@pytest.fixture
async def stage(db_session: AsyncSession, direction: Direction) -> Stage:
    """Create test stage."""
    stage = Stage(
        direction_id=direction.id,
        stage_number=1,
        title="Test Stage",
        planned_duration_days=14,
        is_active=True,
    )
    db_session.add(stage)
    await db_session.commit()
    await db_session.refresh(stage)
    return stage


@pytest.fixture
async def active_student(db_session: AsyncSession) -> Student:
    """Create active student."""
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
    """Create inactive student."""
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


@pytest.fixture
async def student_with_progress(
    db_session: AsyncSession,
    active_student: Student,
    direction: Direction,
    stage: Stage,
) -> tuple[Student, StudentProgress]:
    """Create student with progress."""
    progress = StudentProgress(
        student_id=active_student.id,
        direction_id=direction.id,
        current_stage_id=stage.id,
        started_at=datetime.now(pytz.UTC),
    )
    db_session.add(progress)
    await db_session.commit()
    await db_session.refresh(progress)
    return active_student, progress


@pytest.mark.asyncio
async def test_get_weekly_report_reminders_active_student(
    service: NotificationService,
    active_student: Student,
) -> None:
    """Test weekly report reminder for active student without report."""
    reminders = await service.get_weekly_report_reminders()

    assert len(reminders) == 1
    assert reminders[0].recipient.student_id == active_student.id
    assert reminders[0].recipient.telegram_id == active_student.telegram_id
    assert "еженедельном отчёте" in reminders[0].message


@pytest.mark.asyncio
async def test_get_weekly_report_reminders_excludes_paused(
    service: NotificationService,
    paused_student: Student,
) -> None:
    """Test that paused students don't get reminders."""
    reminders = await service.get_weekly_report_reminders()

    assert len(reminders) == 0


@pytest.mark.asyncio
async def test_get_weekly_report_reminders_excludes_inactive(
    service: NotificationService,
    inactive_student: Student,
) -> None:
    """Test that inactive students don't get reminders."""
    reminders = await service.get_weekly_report_reminders()

    assert len(reminders) == 0


@pytest.mark.asyncio
async def test_get_weekly_report_reminders_excludes_submitted(
    service: NotificationService,
    active_student: Student,
    db_session: AsyncSession,
) -> None:
    """Test that students who submitted report don't get reminder."""
    # Create report for current week
    from sputnik_offer_crm.services.weekly_report import WeeklyReportService

    weekly_service = WeeklyReportService(db_session)
    now = datetime.now(pytz.UTC)
    week_start = weekly_service.get_week_start_date(now, active_student.timezone)

    report = WeeklyReport(
        student_id=active_student.id,
        week_start_date=week_start,
        answer_what_did="Test",
        answer_problems_solved=None,
        answer_problems_unsolved=None,
    )
    db_session.add(report)
    await db_session.commit()

    reminders = await service.get_weekly_report_reminders()

    assert len(reminders) == 0


@pytest.mark.asyncio
async def test_get_weekly_report_reminders_deduplication(
    service: NotificationService,
    active_student: Student,
    db_session: AsyncSession,
) -> None:
    """Test that reminder is not sent twice in same day."""
    # First call - should return reminder
    reminders1 = await service.get_weekly_report_reminders()
    assert len(reminders1) == 1

    # Mark as sent
    await service.mark_weekly_report_reminder_sent(
        active_student.id,
        reminders1[0].week_start_date,
        reminders1[0].message,
    )
    await db_session.commit()

    # Second call - should not return reminder
    reminders2 = await service.get_weekly_report_reminders()
    assert len(reminders2) == 0


@pytest.mark.asyncio
async def test_get_deadline_reminders_upcoming(
    service: NotificationService,
    student_with_progress: tuple[Student, StudentProgress],
    stage: Stage,
    db_session: AsyncSession,
) -> None:
    """Test deadline reminder for upcoming deadline."""
    student, progress = student_with_progress

    # Set deadline in 2 days
    deadline = date.today() + timedelta(days=2)
    stage_progress = StudentStageProgress(
        student_id=student.id,
        stage_id=stage.id,
        status="active",
        started_at=date.today(),
        planned_deadline=deadline,
    )
    db_session.add(stage_progress)
    await db_session.commit()

    reminders = await service.get_deadline_reminders(upcoming_days=3)

    assert len(reminders) == 1
    assert reminders[0].recipient.student_id == student.id
    assert reminders[0].is_overdue is False
    assert reminders[0].days_until == 2
    assert "Напоминание о дедлайне" in reminders[0].message


@pytest.mark.asyncio
async def test_get_deadline_reminders_overdue(
    service: NotificationService,
    student_with_progress: tuple[Student, StudentProgress],
    stage: Stage,
    db_session: AsyncSession,
) -> None:
    """Test deadline reminder for overdue deadline."""
    student, progress = student_with_progress

    # Set deadline 2 days ago
    deadline = date.today() - timedelta(days=2)
    stage_progress = StudentStageProgress(
        student_id=student.id,
        stage_id=stage.id,
        status="active",
        started_at=date.today() - timedelta(days=10),
        planned_deadline=deadline,
    )
    db_session.add(stage_progress)
    await db_session.commit()

    reminders = await service.get_deadline_reminders()

    assert len(reminders) == 1
    assert reminders[0].recipient.student_id == student.id
    assert reminders[0].is_overdue is True
    assert reminders[0].days_until == -2
    assert "просрочен" in reminders[0].message


@pytest.mark.asyncio
async def test_get_deadline_reminders_excludes_paused(
    service: NotificationService,
    paused_student: Student,
    direction: Direction,
    stage: Stage,
    db_session: AsyncSession,
) -> None:
    """Test that paused students don't get deadline reminders."""
    # Create progress for paused student
    progress = StudentProgress(
        student_id=paused_student.id,
        direction_id=direction.id,
        current_stage_id=stage.id,
        started_at=datetime.now(pytz.UTC),
    )
    db_session.add(progress)

    deadline = date.today() + timedelta(days=1)
    stage_progress = StudentStageProgress(
        student_id=paused_student.id,
        stage_id=stage.id,
        status="active",
        started_at=date.today(),
        planned_deadline=deadline,
    )
    db_session.add(stage_progress)
    await db_session.commit()

    reminders = await service.get_deadline_reminders()

    assert len(reminders) == 0


@pytest.mark.asyncio
async def test_get_deadline_reminders_deduplication(
    service: NotificationService,
    student_with_progress: tuple[Student, StudentProgress],
    stage: Stage,
    db_session: AsyncSession,
) -> None:
    """Test that deadline reminder is not sent twice in same day."""
    student, progress = student_with_progress

    deadline = date.today() + timedelta(days=1)
    stage_progress = StudentStageProgress(
        student_id=student.id,
        stage_id=stage.id,
        status="active",
        started_at=date.today(),
        planned_deadline=deadline,
    )
    db_session.add(stage_progress)
    await db_session.commit()

    # First call - should return reminder
    reminders1 = await service.get_deadline_reminders()
    assert len(reminders1) == 1

    # Mark as sent
    await service.mark_deadline_reminder_sent(
        student.id,
        stage.id,
        deadline,
        reminders1[0].is_overdue,
        reminders1[0].message,
    )
    await db_session.commit()

    # Second call - should not return reminder
    reminders2 = await service.get_deadline_reminders()
    assert len(reminders2) == 0


@pytest.mark.asyncio
async def test_notification_log_created(
    service: NotificationService,
    active_student: Student,
    db_session: AsyncSession,
) -> None:
    """Test that notification log is created."""
    from sqlalchemy import select

    week_start = date.today()
    message = "Test message"

    await service.mark_weekly_report_reminder_sent(
        active_student.id,
        week_start,
        message,
    )
    await db_session.commit()

    result = await db_session.execute(
        select(NotificationLog).where(
            NotificationLog.student_id == active_student.id
        )
    )
    log = result.scalar_one()

    assert log.notification_type == "weekly_report_reminder"
    assert log.notification_key == week_start.isoformat()
    assert log.message == message


@pytest.mark.asyncio
async def test_get_task_reminders_upcoming(
    service: NotificationService,
    active_student: Student,
    db_session: AsyncSession,
) -> None:
    """Test task reminder for upcoming deadline."""
    # Create task with deadline in 2 days
    deadline = date.today() + timedelta(days=2)
    task = StudentTask(
        student_id=active_student.id,
        title="Test Task",
        description="Test description",
        deadline=deadline,
        status=TaskStatus.OPEN.value,
    )
    db_session.add(task)
    await db_session.commit()

    reminders = await service.get_task_reminders(upcoming_days=3)

    assert len(reminders) == 1
    assert reminders[0].recipient.student_id == active_student.id
    assert reminders[0].task_id == task.id
    assert reminders[0].is_overdue is False
    assert reminders[0].days_until == 2
    assert "Напоминание о задаче" in reminders[0].message
    assert task.title in reminders[0].message


@pytest.mark.asyncio
async def test_get_task_reminders_overdue(
    service: NotificationService,
    active_student: Student,
    db_session: AsyncSession,
) -> None:
    """Test task reminder for overdue deadline."""
    # Create task with deadline 2 days ago
    deadline = date.today() - timedelta(days=2)
    task = StudentTask(
        student_id=active_student.id,
        title="Overdue Task",
        description="Test description",
        deadline=deadline,
        status=TaskStatus.OPEN.value,
    )
    db_session.add(task)
    await db_session.commit()

    reminders = await service.get_task_reminders()

    assert len(reminders) == 1
    assert reminders[0].recipient.student_id == active_student.id
    assert reminders[0].task_id == task.id
    assert reminders[0].is_overdue is True
    assert reminders[0].days_until == -2
    assert "просрочена" in reminders[0].message


@pytest.mark.asyncio
async def test_get_task_reminders_excludes_done(
    service: NotificationService,
    active_student: Student,
    db_session: AsyncSession,
) -> None:
    """Test that done tasks don't get reminders."""
    deadline = date.today() + timedelta(days=1)
    task = StudentTask(
        student_id=active_student.id,
        title="Done Task",
        deadline=deadline,
        status=TaskStatus.DONE.value,
    )
    db_session.add(task)
    await db_session.commit()

    reminders = await service.get_task_reminders()

    assert len(reminders) == 0


@pytest.mark.asyncio
async def test_get_task_reminders_excludes_cancelled(
    service: NotificationService,
    active_student: Student,
    db_session: AsyncSession,
) -> None:
    """Test that cancelled tasks don't get reminders."""
    deadline = date.today() + timedelta(days=1)
    task = StudentTask(
        student_id=active_student.id,
        title="Cancelled Task",
        deadline=deadline,
        status=TaskStatus.CANCELLED.value,
    )
    db_session.add(task)
    await db_session.commit()

    reminders = await service.get_task_reminders()

    assert len(reminders) == 0


@pytest.mark.asyncio
async def test_get_task_reminders_excludes_no_deadline(
    service: NotificationService,
    active_student: Student,
    db_session: AsyncSession,
) -> None:
    """Test that tasks without deadline don't get reminders."""
    task = StudentTask(
        student_id=active_student.id,
        title="No Deadline Task",
        deadline=None,
        status=TaskStatus.OPEN.value,
    )
    db_session.add(task)
    await db_session.commit()

    reminders = await service.get_task_reminders()

    assert len(reminders) == 0


@pytest.mark.asyncio
async def test_get_task_reminders_excludes_paused(
    service: NotificationService,
    paused_student: Student,
    db_session: AsyncSession,
) -> None:
    """Test that paused students don't get task reminders."""
    deadline = date.today() + timedelta(days=1)
    task = StudentTask(
        student_id=paused_student.id,
        title="Task for Paused Student",
        deadline=deadline,
        status=TaskStatus.OPEN.value,
    )
    db_session.add(task)
    await db_session.commit()

    reminders = await service.get_task_reminders()

    assert len(reminders) == 0


@pytest.mark.asyncio
async def test_get_task_reminders_excludes_inactive(
    service: NotificationService,
    inactive_student: Student,
    db_session: AsyncSession,
) -> None:
    """Test that inactive students don't get task reminders."""
    deadline = date.today() + timedelta(days=1)
    task = StudentTask(
        student_id=inactive_student.id,
        title="Task for Inactive Student",
        deadline=deadline,
        status=TaskStatus.OPEN.value,
    )
    db_session.add(task)
    await db_session.commit()

    reminders = await service.get_task_reminders()

    assert len(reminders) == 0


@pytest.mark.asyncio
async def test_get_task_reminders_deduplication(
    service: NotificationService,
    active_student: Student,
    db_session: AsyncSession,
) -> None:
    """Test that task reminder is not sent twice in same day."""
    deadline = date.today() + timedelta(days=1)
    task = StudentTask(
        student_id=active_student.id,
        title="Test Task",
        deadline=deadline,
        status=TaskStatus.OPEN.value,
    )
    db_session.add(task)
    await db_session.commit()

    # First call - should return reminder
    reminders1 = await service.get_task_reminders()
    assert len(reminders1) == 1

    # Mark as sent
    await service.mark_task_reminder_sent(
        active_student.id,
        task.id,
        deadline,
        reminders1[0].is_overdue,
        reminders1[0].message,
    )
    await db_session.commit()

    # Second call - should not return reminder
    reminders2 = await service.get_task_reminders()
    assert len(reminders2) == 0


@pytest.mark.asyncio
async def test_get_task_reminders_multiple_tasks(
    service: NotificationService,
    active_student: Student,
    db_session: AsyncSession,
) -> None:
    """Test multiple task reminders for same student."""
    # Create two tasks with upcoming deadlines
    task1 = StudentTask(
        student_id=active_student.id,
        title="Task 1",
        deadline=date.today() + timedelta(days=1),
        status=TaskStatus.OPEN.value,
    )
    task2 = StudentTask(
        student_id=active_student.id,
        title="Task 2",
        deadline=date.today() + timedelta(days=2),
        status=TaskStatus.OPEN.value,
    )
    db_session.add_all([task1, task2])
    await db_session.commit()

    reminders = await service.get_task_reminders(upcoming_days=3)

    assert len(reminders) == 2
    task_ids = {r.task_id for r in reminders}
    assert task1.id in task_ids
    assert task2.id in task_ids

