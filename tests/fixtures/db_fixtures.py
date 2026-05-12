"""Database fixtures for tests."""

from datetime import date, datetime, timezone

import pytest_asyncio

from sputnik_offer_crm.models import (
    Direction,
    DirectionStage,
    InviteCode,
    Mentor,
    Stage,
    Student,
    StudentProgress,
    StudentStageProgress,
    StudentTask,
    WeeklyReport,
)


@pytest_asyncio.fixture
async def direction(db_session) -> Direction:
    """Create test direction."""
    direction = Direction(
        code="python",
        name="Python Development",
        is_active=True,
    )
    db_session.add(direction)
    await db_session.commit()
    await db_session.refresh(direction)
    return direction


@pytest_asyncio.fixture
async def stage(db_session, direction) -> Stage:
    """Create test stage (db-schema.txt format)."""
    stage = Stage(
        direction_id=direction.id,
        stage_number=1,
        title="Основы Python",
        description="Изучение базового синтаксиса",
        planned_duration_days=30,
        is_active=True,
    )
    db_session.add(stage)
    await db_session.commit()
    await db_session.refresh(stage)
    return stage


@pytest_asyncio.fixture
async def direction_stage(db_session, direction) -> DirectionStage:
    """Create test direction stage (deprecated, use 'stage' fixture instead)."""
    stage = DirectionStage(
        direction_id=direction.id,
        name="Основы Python",
        order_index=0,
        is_active=True,
        is_final=False,
    )
    db_session.add(stage)
    await db_session.commit()
    await db_session.refresh(stage)
    return stage


@pytest_asyncio.fixture
async def mentor(db_session) -> Mentor:
    """Create test mentor."""
    mentor = Mentor(
        telegram_id=123456789,
        first_name="Иван",
        last_name="Петров",
        username="mentor_ivan",
        is_active=True,
    )
    db_session.add(mentor)
    await db_session.commit()
    await db_session.refresh(mentor)
    return mentor


@pytest_asyncio.fixture
async def student(db_session) -> Student:
    """Create test student."""
    student = Student(
        telegram_id=987654321,
        first_name="Алексей",
        last_name="Сидоров",
        username="student_alex",
        timezone="Europe/Moscow",
        is_active=True,
    )
    db_session.add(student)
    await db_session.commit()
    await db_session.refresh(student)
    return student


@pytest_asyncio.fixture
async def invite_code(db_session, mentor, direction) -> InviteCode:
    """Create test invite code."""
    code = InviteCode(
        code="TEST1234",
        mentor_id=mentor.id,
        direction_id=direction.id,
        suggested_timezone="Europe/Moscow",
        used_at=None,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(code)
    await db_session.commit()
    await db_session.refresh(code)
    return code


@pytest_asyncio.fixture
async def used_invite_code(db_session, mentor, direction) -> InviteCode:
    """Create used invite code."""
    code = InviteCode(
        code="USED5678",
        mentor_id=mentor.id,
        direction_id=direction.id,
        suggested_timezone="Europe/Moscow",
        used_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(code)
    await db_session.commit()
    await db_session.refresh(code)
    return code


@pytest_asyncio.fixture
async def student_progress(db_session, student, direction, stage) -> StudentProgress:
    """Create test student progress."""
    progress = StudentProgress(
        student_id=student.id,
        direction_id=direction.id,
        current_stage_id=stage.id,
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(progress)
    await db_session.commit()
    await db_session.refresh(progress)
    return progress


@pytest_asyncio.fixture
async def student_stage_progress(db_session, student, stage) -> StudentStageProgress:
    """Create test student stage progress."""
    from datetime import date

    progress = StudentStageProgress(
        student_id=student.id,
        stage_id=stage.id,
        status="active",
        started_at=date(2026, 5, 1),
        planned_deadline=date(2026, 6, 1),
    )
    db_session.add(progress)
    await db_session.commit()
    await db_session.refresh(progress)
    return progress


@pytest_asyncio.fixture
async def student_task(db_session, student) -> StudentTask:
    """Create test student task."""
    from datetime import date

    task = StudentTask(
        student_id=student.id,
        task_order=1,
        title="Решить задачу на списки",
        description="Написать функцию для работы со списками",
        deadline=date(2026, 5, 20),
        status="open",
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    return task


@pytest_asyncio.fixture
async def weekly_report(db_session, student) -> WeeklyReport:
    """Create test weekly report."""
    report = WeeklyReport(
        student_id=student.id,
        week_start_date=date(2026, 5, 12),  # Monday
        answer_what_did="Изучал Python",
        answer_problems_solved="Решил проблему с async",
        answer_problems_unsolved=None,
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)
    return report
