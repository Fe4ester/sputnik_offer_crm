"""Tests for student cabinet enhancements."""

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from sputnik_offer_crm.models import (
    Direction,
    Stage,
    Student,
    StudentProgress,
    StudentStageProgress,
    StudentStatus,
)
from sputnik_offer_crm.services.student import StudentService


@pytest.fixture
async def direction(db_session: AsyncSession) -> Direction:
    """Create test direction."""
    direction = Direction(
        name="Test Direction",
        code="TEST",
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
        title="Stage 1",
        stage_number=1,
    )
    stage2 = Stage(
        direction_id=direction.id,
        title="Stage 2",
        stage_number=2,
    )
    stage3 = Stage(
        direction_id=direction.id,
        title="Stage 3",
        stage_number=3,
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
def service(db_session: AsyncSession) -> StudentService:
    """Create service instance."""
    return StudentService(db_session)


@pytest.mark.asyncio
async def test_get_completed_stages_count_no_completed(
    service: StudentService,
    student: Student,
    student_progress: StudentProgress,
    stages: list[Stage],
) -> None:
    """Test getting completed stages count when none completed."""
    completed, total = await service.get_completed_stages_count(student.telegram_id)

    assert total == 3
    assert completed == 0


@pytest.mark.asyncio
async def test_get_completed_stages_count_with_completed(
    service: StudentService,
    student: Student,
    student_progress: StudentProgress,
    stages: list[Stage],
    db_session: AsyncSession,
) -> None:
    """Test getting completed stages count with some completed."""
    # Mark stage 1 as completed
    stage_progress = StudentStageProgress(
        student_id=student.id,
        stage_id=stages[0].id,
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(stage_progress)
    await db_session.commit()

    completed, total = await service.get_completed_stages_count(student.telegram_id)

    assert total == 3
    assert completed == 1


@pytest.mark.asyncio
async def test_get_completed_stages_count_student_not_found(
    service: StudentService,
) -> None:
    """Test getting completed stages count for non-existent student."""
    completed, total = await service.get_completed_stages_count(99999)

    assert completed == 0
    assert total == 0


@pytest.mark.asyncio
async def test_get_stages_overview_basic(
    service: StudentService,
    student: Student,
    student_progress: StudentProgress,
    stages: list[Stage],
) -> None:
    """Test getting stages overview."""
    overview = await service.get_stages_overview(student.telegram_id)

    assert len(overview) == 3

    # Stage 1 should be completed (before current)
    assert overview[0].stage.id == stages[0].id
    assert overview[0].status == "completed"

    # Stage 2 should be current
    assert overview[1].stage.id == stages[1].id
    assert overview[1].status == "current"

    # Stage 3 should be upcoming
    assert overview[2].stage.id == stages[2].id
    assert overview[2].status == "upcoming"


@pytest.mark.asyncio
async def test_get_stages_overview_with_deadlines(
    service: StudentService,
    student: Student,
    student_progress: StudentProgress,
    stages: list[Stage],
    db_session: AsyncSession,
) -> None:
    """Test getting stages overview with deadlines."""
    # Add deadline to stage 2 (current)
    stage_progress = StudentStageProgress(
        student_id=student.id,
        stage_id=stages[1].id,
        planned_deadline=date.today() + timedelta(days=7),
    )
    db_session.add(stage_progress)
    await db_session.commit()

    overview = await service.get_stages_overview(student.telegram_id)

    # Stage 2 should have deadline
    assert overview[1].deadline == date.today() + timedelta(days=7)
    assert overview[1].is_overdue is False


@pytest.mark.asyncio
async def test_get_stages_overview_with_overdue_deadline(
    service: StudentService,
    student: Student,
    student_progress: StudentProgress,
    stages: list[Stage],
    db_session: AsyncSession,
) -> None:
    """Test getting stages overview with overdue deadline."""
    # Add overdue deadline to stage 2 (current)
    stage_progress = StudentStageProgress(
        student_id=student.id,
        stage_id=stages[1].id,
        planned_deadline=date.today() - timedelta(days=7),
    )
    db_session.add(stage_progress)
    await db_session.commit()

    overview = await service.get_stages_overview(student.telegram_id)

    # Stage 2 should have overdue deadline
    assert overview[1].deadline == date.today() - timedelta(days=7)
    assert overview[1].is_overdue is True


@pytest.mark.asyncio
async def test_get_stages_overview_with_completed_stage(
    service: StudentService,
    student: Student,
    student_progress: StudentProgress,
    stages: list[Stage],
    db_session: AsyncSession,
) -> None:
    """Test getting stages overview with explicitly completed stage."""
    # Mark stage 1 as completed
    stage_progress = StudentStageProgress(
        student_id=student.id,
        stage_id=stages[0].id,
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(stage_progress)
    await db_session.commit()

    overview = await service.get_stages_overview(student.telegram_id)

    # Stage 1 should be completed
    assert overview[0].status == "completed"


@pytest.mark.asyncio
async def test_get_stages_overview_student_not_found(
    service: StudentService,
) -> None:
    """Test getting stages overview for non-existent student."""
    overview = await service.get_stages_overview(99999)

    assert overview == []


@pytest.mark.asyncio
async def test_get_stages_overview_ordered_by_stage_order(
    service: StudentService,
    student: Student,
    student_progress: StudentProgress,
    stages: list[Stage],
) -> None:
    """Test that stages overview is ordered by stage number."""
    overview = await service.get_stages_overview(student.telegram_id)

    assert len(overview) == 3
    assert overview[0].stage.stage_number == 1
    assert overview[1].stage.stage_number == 2
    assert overview[2].stage.stage_number == 3
