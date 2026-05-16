"""Tests for detailed progress view."""

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from sputnik_offer_crm.models import (
    Direction,
    Stage,
    Student,
    StudentProgress,
    StudentStageProgress,
    StudentStatus,
    StudentTask,
    TaskStatus,
    WeeklyReport,
)
from sputnik_offer_crm.services.mentor_student import MentorStudentService


@pytest.fixture
async def direction(db_session: AsyncSession) -> Direction:
    """Create test direction."""
    direction = Direction(
        code="test",
        name="Test Direction",
        is_active=True,
    )
    db_session.add(direction)
    await db_session.commit()
    await db_session.refresh(direction)
    return direction


@pytest.fixture
async def stages(db_session: AsyncSession, direction: Direction) -> list[Stage]:
    """Create test stages."""
    stage1 = Stage(
        direction_id=direction.id,
        stage_number=1,
        title="Stage 1",
        is_active=True,
    )
    stage2 = Stage(
        direction_id=direction.id,
        stage_number=2,
        title="Stage 2",
        is_active=True,
    )
    stage3 = Stage(
        direction_id=direction.id,
        stage_number=3,
        title="Stage 3",
        is_active=True,
    )
    db_session.add_all([stage1, stage2, stage3])
    await db_session.commit()
    await db_session.refresh(stage1)
    await db_session.refresh(stage2)
    await db_session.refresh(stage3)
    return [stage1, stage2, stage3]


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
async def student_progress(
    db_session: AsyncSession,
    student: Student,
    direction: Direction,
    stages: list[Stage],
) -> StudentProgress:
    """Create test student progress."""
    progress = StudentProgress(
        student_id=student.id,
        direction_id=direction.id,
        current_stage_id=stages[1].id,  # Stage 2 is current
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(progress)
    await db_session.commit()
    await db_session.refresh(progress)
    return progress


@pytest.fixture
def service(db_session: AsyncSession) -> MentorStudentService:
    """Create service instance."""
    return MentorStudentService(db_session)


@pytest.mark.asyncio
async def test_get_detailed_progress_basic(
    service: MentorStudentService,
    student: Student,
    student_progress: StudentProgress,
    stages: list[Stage],
) -> None:
    """Test getting basic detailed progress."""
    detailed = await service.get_detailed_progress(student.id)

    assert detailed is not None
    assert detailed.student.id == student.id
    assert detailed.current_stage.id == stages[1].id
    assert detailed.total_stages_count == 3
    # Stage 1 is before current, so counted as completed
    assert detailed.completed_stages_count == 1


@pytest.mark.asyncio
async def test_get_detailed_progress_with_completed_stage(
    service: MentorStudentService,
    student: Student,
    student_progress: StudentProgress,
    stages: list[Stage],
    db_session: AsyncSession,
) -> None:
    """Test detailed progress with completed stage."""
    # Mark stage 1 as completed
    stage_progress = StudentStageProgress(
        student_id=student.id,
        stage_id=stages[0].id,
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(stage_progress)
    await db_session.commit()

    detailed = await service.get_detailed_progress(student.id)

    assert detailed.completed_stages_count == 1
    assert detailed.all_stages[0][1] == "completed"
    assert detailed.all_stages[1][1] == "current"
    assert detailed.all_stages[2][1] == "upcoming"


@pytest.mark.asyncio
async def test_get_detailed_progress_with_tasks(
    service: MentorStudentService,
    student: Student,
    student_progress: StudentProgress,
    db_session: AsyncSession,
) -> None:
    """Test detailed progress with tasks."""
    # Create tasks
    task1 = StudentTask(
        student_id=student.id,
        title="Task 1",
        status=TaskStatus.OPEN.value,
    )
    task2 = StudentTask(
        student_id=student.id,
        title="Task 2",
        status=TaskStatus.DONE.value,
    )
    task3 = StudentTask(
        student_id=student.id,
        title="Task 3",
        status=TaskStatus.CANCELLED.value,
    )
    db_session.add_all([task1, task2, task3])
    await db_session.commit()

    detailed = await service.get_detailed_progress(student.id)

    assert detailed.tasks_summary["open"] == 1
    assert detailed.tasks_summary["done"] == 1
    assert detailed.tasks_summary["cancelled"] == 1


@pytest.mark.asyncio
async def test_get_detailed_progress_with_reports(
    service: MentorStudentService,
    student: Student,
    student_progress: StudentProgress,
    db_session: AsyncSession,
) -> None:
    """Test detailed progress with reports."""
    # Create reports
    from datetime import date

    report1 = WeeklyReport(
        student_id=student.id,
        week_start_date=date.today(),
        answer_what_did="Work done",
    )
    report2 = WeeklyReport(
        student_id=student.id,
        week_start_date=date(2024, 1, 1),
        answer_what_did="Old work",
    )
    db_session.add_all([report1, report2])
    await db_session.commit()

    detailed = await service.get_detailed_progress(student.id)

    assert detailed.recent_reports_count == 2


@pytest.mark.asyncio
async def test_get_detailed_progress_student_not_found(
    service: MentorStudentService,
) -> None:
    """Test getting detailed progress for non-existent student."""
    detailed = await service.get_detailed_progress(99999)

    assert detailed is None


@pytest.mark.asyncio
async def test_get_detailed_progress_stages_with_deadlines(
    service: MentorStudentService,
    student: Student,
    student_progress: StudentProgress,
    stages: list[Stage],
    db_session: AsyncSession,
) -> None:
    """Test detailed progress with stage deadlines."""
    from datetime import date, timedelta

    # Add deadline to stage 2
    stage_progress = StudentStageProgress(
        student_id=student.id,
        stage_id=stages[1].id,
        planned_deadline=date.today() + timedelta(days=7),
    )
    db_session.add(stage_progress)
    await db_session.commit()

    detailed = await service.get_detailed_progress(student.id)

    # Find stage 2 in all_stages
    stage2_info = next(s for s in detailed.all_stages if s[0].id == stages[1].id)
    assert stage2_info[2] == date.today() + timedelta(days=7)


@pytest.mark.asyncio
async def test_get_detailed_progress_no_tasks(
    service: MentorStudentService,
    student: Student,
    student_progress: StudentProgress,
) -> None:
    """Test detailed progress with no tasks."""
    detailed = await service.get_detailed_progress(student.id)

    assert detailed.tasks_summary["open"] == 0
    assert detailed.tasks_summary["done"] == 0
    assert detailed.tasks_summary["cancelled"] == 0
    assert detailed.tasks_summary["overdue"] == 0


@pytest.mark.asyncio
async def test_get_detailed_progress_no_reports(
    service: MentorStudentService,
    student: Student,
    student_progress: StudentProgress,
) -> None:
    """Test detailed progress with no reports."""
    detailed = await service.get_detailed_progress(student.id)

    assert detailed.recent_reports_count == 0
