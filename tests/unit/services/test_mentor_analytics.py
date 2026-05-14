"""Tests for MentorAnalyticsService."""

from datetime import date, datetime, timedelta

import pytest
import pytz
from sqlalchemy.ext.asyncio import AsyncSession

from sputnik_offer_crm.models import (
    Direction,
    Stage,
    Student,
    StudentProgress,
    StudentStageProgress,
)
from sputnik_offer_crm.services.mentor_analytics import MentorAnalyticsService


@pytest.fixture
def service(db_session: AsyncSession) -> MentorAnalyticsService:
    """Create service instance."""
    return MentorAnalyticsService(db_session)


@pytest.fixture
async def direction(db_session: AsyncSession) -> Direction:
    """Create test direction."""
    direction = Direction(code="python", name="Python Backend", is_active=True)
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
        title="Stage 1",
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
        first_name="Active",
        last_name="Student",
        username="activestudent",
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
async def dropped_student(db_session: AsyncSession) -> Student:
    """Create dropped student."""
    from sputnik_offer_crm.models import StudentStatus
    student = Student(
        telegram_id=111222333,
        first_name="Dropped",
        last_name="Student",
        username="droppedstudent",
        timezone="Europe/Moscow",
    )
    student.set_status(StudentStatus.DROPPED)
    db_session.add(student)
    await db_session.commit()
    await db_session.refresh(student)
    return student


@pytest.fixture
async def completed_student(db_session: AsyncSession) -> Student:
    """Create completed student with offer."""
    from sputnik_offer_crm.models import StudentStatus
    student = Student(
        telegram_id=444555666,
        first_name="Completed",
        last_name="Student",
        username="completedstudent",
        timezone="Europe/Moscow",
        offer_company="Test Company",
        offer_position="Developer",
        offer_received_at=datetime.now(pytz.UTC),
    )
    student.set_status(StudentStatus.ACTIVE)
    db_session.add(student)
    await db_session.commit()
    await db_session.refresh(student)
    return student


@pytest.mark.asyncio
async def test_get_direction_summaries_empty(
    service: MentorAnalyticsService,
) -> None:
    """Test getting summaries when no data exists."""
    summaries = await service.get_direction_summaries()
    assert len(summaries) == 0


@pytest.mark.asyncio
async def test_get_direction_summaries_with_students(
    service: MentorAnalyticsService,
    direction: Direction,
    stage: Stage,
    active_student: Student,
    paused_student: Student,
    dropped_student: Student,
    completed_student: Student,
    db_session: AsyncSession,
) -> None:
    """Test getting summaries with various student states."""
    # Create progress for all students
    for student in [active_student, paused_student, dropped_student, completed_student]:
        progress = StudentProgress(
            student_id=student.id,
            direction_id=direction.id,
            current_stage_id=stage.id,
            started_at=datetime.now(pytz.UTC),
        )
        db_session.add(progress)
    await db_session.commit()

    summaries = await service.get_direction_summaries()

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.direction_code == "python"
    assert summary.direction_name == "Python Backend"
    assert summary.total_students == 4
    assert summary.active_students == 2  # active_student + completed_student
    assert summary.paused_students == 1  # paused_student
    assert summary.dropped_students == 1  # dropped_student
    assert summary.completed_with_offer == 1  # completed_student


@pytest.mark.asyncio
async def test_get_stage_progress_empty(
    service: MentorAnalyticsService,
    direction: Direction,
    stage: Stage,
) -> None:
    """Test getting stage progress with no students."""
    progress = await service.get_stage_progress()

    assert len(progress) == 1
    assert progress[0].direction_code == "python"
    assert progress[0].stage_number == 1
    assert progress[0].students_count == 0


@pytest.mark.asyncio
async def test_get_stage_progress_with_students(
    service: MentorAnalyticsService,
    direction: Direction,
    stage: Stage,
    active_student: Student,
    paused_student: Student,
    db_session: AsyncSession,
) -> None:
    """Test getting stage progress with students."""
    # Create progress for active student only (paused students are excluded)
    progress = StudentProgress(
        student_id=active_student.id,
        direction_id=direction.id,
        current_stage_id=stage.id,
        started_at=datetime.now(pytz.UTC),
    )
    db_session.add(progress)
    await db_session.commit()

    progress_list = await service.get_stage_progress()

    assert len(progress_list) == 1
    assert progress_list[0].students_count == 1  # Only active student counted


@pytest.mark.asyncio
async def test_get_all_deadlines_empty(
    service: MentorAnalyticsService,
) -> None:
    """Test getting deadlines when none exist."""
    deadlines = await service.get_all_deadlines()
    assert len(deadlines) == 0


@pytest.mark.asyncio
async def test_get_all_deadlines_with_data(
    service: MentorAnalyticsService,
    direction: Direction,
    stage: Stage,
    active_student: Student,
    db_session: AsyncSession,
) -> None:
    """Test getting deadlines with active deadlines."""
    # Create progress
    progress = StudentProgress(
        student_id=active_student.id,
        direction_id=direction.id,
        current_stage_id=stage.id,
        started_at=datetime.now(pytz.UTC),
    )
    db_session.add(progress)

    # Create stage progress with deadline
    deadline = date.today() + timedelta(days=7)
    stage_progress = StudentStageProgress(
        student_id=active_student.id,
        stage_id=stage.id,
        status="active",
        started_at=date.today(),
        planned_deadline=deadline,
    )
    db_session.add(stage_progress)
    await db_session.commit()

    deadlines = await service.get_all_deadlines()

    assert len(deadlines) == 1
    assert deadlines[0].student_name == "Active Student"
    assert deadlines[0].direction_name == "Python Backend"
    assert deadlines[0].stage_title == "Stage 1"
    assert deadlines[0].deadline_date == deadline
    assert deadlines[0].is_overdue is False


@pytest.mark.asyncio
async def test_get_all_deadlines_overdue(
    service: MentorAnalyticsService,
    direction: Direction,
    stage: Stage,
    active_student: Student,
    db_session: AsyncSession,
) -> None:
    """Test getting overdue deadlines."""
    # Create progress
    progress = StudentProgress(
        student_id=active_student.id,
        direction_id=direction.id,
        current_stage_id=stage.id,
        started_at=datetime.now(pytz.UTC),
    )
    db_session.add(progress)

    # Create stage progress with overdue deadline
    deadline = date.today() - timedelta(days=2)
    stage_progress = StudentStageProgress(
        student_id=active_student.id,
        stage_id=stage.id,
        status="active",
        started_at=date.today() - timedelta(days=10),
        planned_deadline=deadline,
    )
    db_session.add(stage_progress)
    await db_session.commit()

    deadlines = await service.get_all_deadlines()

    assert len(deadlines) == 1
    assert deadlines[0].is_overdue is True


@pytest.mark.asyncio
async def test_export_to_csv(
    service: MentorAnalyticsService,
    direction: Direction,
    stage: Stage,
    active_student: Student,
    db_session: AsyncSession,
) -> None:
    """Test CSV export."""
    # Create progress
    progress = StudentProgress(
        student_id=active_student.id,
        direction_id=direction.id,
        current_stage_id=stage.id,
        started_at=datetime.now(pytz.UTC),
    )
    db_session.add(progress)

    # Create stage progress with deadline
    deadline = date.today() + timedelta(days=7)
    stage_progress = StudentStageProgress(
        student_id=active_student.id,
        stage_id=stage.id,
        status="active",
        started_at=date.today(),
        planned_deadline=deadline,
    )
    db_session.add(stage_progress)
    await db_session.commit()

    directions_csv, stages_csv, deadlines_csv = await service.export_to_csv()

    # Check that CSVs are not empty
    assert len(directions_csv) > 0
    assert len(stages_csv) > 0
    assert len(deadlines_csv) > 0

    # Check headers
    assert "Направление (код)" in directions_csv
    assert "Номер этапа" in stages_csv
    assert "Дедлайн" in deadlines_csv

    # Check data
    assert "python" in directions_csv
    assert "Python Backend" in directions_csv
    assert "Stage 1" in stages_csv
    assert "Active Student" in deadlines_csv
