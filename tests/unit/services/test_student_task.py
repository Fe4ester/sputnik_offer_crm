"""Tests for StudentTaskService."""

from datetime import date, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from sputnik_offer_crm.models import Student, StudentStatus, StudentTask
from sputnik_offer_crm.services.student_task import (
    StudentNotFoundError,
    StudentTaskService,
)


@pytest.fixture
def service(db_session: AsyncSession) -> StudentTaskService:
    """Create service instance."""
    return StudentTaskService(db_session)


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


@pytest.mark.asyncio
async def test_create_task_minimal(
    service: StudentTaskService,
    student: Student,
) -> None:
    """Test creating task with minimal fields."""
    task = await service.create_task(
        student_id=student.id,
        title="Complete homework",
    )

    assert task.id is not None
    assert task.student_id == student.id
    assert task.title == "Complete homework"
    assert task.description is None
    assert task.deadline is None
    assert task.mentor_task is None
    assert task.status == "open"
    assert task.completed_at is None


@pytest.mark.asyncio
async def test_create_task_full(
    service: StudentTaskService,
    student: Student,
) -> None:
    """Test creating task with all fields."""
    deadline = date.today() + timedelta(days=7)
    task = await service.create_task(
        student_id=student.id,
        title="Complete project",
        description="Build a REST API",
        deadline=deadline,
        mentor_task="Review code quality",
    )

    assert task.id is not None
    assert task.student_id == student.id
    assert task.title == "Complete project"
    assert task.description == "Build a REST API"
    assert task.deadline == deadline
    assert task.mentor_task == "Review code quality"
    assert task.status == "open"


@pytest.mark.asyncio
async def test_create_task_strips_whitespace(
    service: StudentTaskService,
    student: Student,
) -> None:
    """Test that create_task strips whitespace."""
    task = await service.create_task(
        student_id=student.id,
        title="  Task title  ",
        description="  Task description  ",
        mentor_task="  Mentor task  ",
    )

    assert task.title == "Task title"
    assert task.description == "Task description"
    assert task.mentor_task == "Mentor task"


@pytest.mark.asyncio
async def test_create_task_student_not_found(
    service: StudentTaskService,
) -> None:
    """Test error when student not found."""
    with pytest.raises(StudentNotFoundError):
        await service.create_task(
            student_id=99999,
            title="Task",
        )


@pytest.mark.asyncio
async def test_get_student_tasks_empty(
    service: StudentTaskService,
    student: Student,
) -> None:
    """Test getting tasks when student has none."""
    tasks = await service.get_student_tasks(student.id)
    assert tasks == []


@pytest.mark.asyncio
async def test_get_student_tasks_multiple(
    service: StudentTaskService,
    student: Student,
    db_session: AsyncSession,
) -> None:
    """Test getting multiple tasks."""
    # Create tasks
    task1 = StudentTask(
        student_id=student.id,
        title="Task 1",
        status="open",
    )
    task2 = StudentTask(
        student_id=student.id,
        title="Task 2",
        description="Description 2",
        deadline=date.today() + timedelta(days=3),
        status="open",
    )
    task3 = StudentTask(
        student_id=student.id,
        title="Task 3",
        status="done",
    )
    db_session.add_all([task1, task2, task3])
    await db_session.commit()

    tasks = await service.get_student_tasks(student.id)

    assert len(tasks) == 3
    # Ordered by created_at desc, so task3 is first
    assert tasks[0].title == "Task 3"
    assert tasks[0].status == "done"
    assert tasks[1].title == "Task 2"
    assert tasks[1].description == "Description 2"
    assert tasks[1].deadline == date.today() + timedelta(days=3)
    assert tasks[2].title == "Task 1"


@pytest.mark.asyncio
async def test_get_student_tasks_student_not_found(
    service: StudentTaskService,
) -> None:
    """Test error when student not found."""
    with pytest.raises(StudentNotFoundError):
        await service.get_student_tasks(99999)


@pytest.mark.asyncio
async def test_get_student_tasks_by_telegram_id(
    service: StudentTaskService,
    student: Student,
    db_session: AsyncSession,
) -> None:
    """Test getting tasks by telegram_id."""
    # Create task
    task = StudentTask(
        student_id=student.id,
        title="Task",
        status="open",
    )
    db_session.add(task)
    await db_session.commit()

    tasks = await service.get_student_tasks_by_telegram_id(student.telegram_id)

    assert len(tasks) == 1
    assert tasks[0].title == "Task"


@pytest.mark.asyncio
async def test_get_student_tasks_by_telegram_id_not_found(
    service: StudentTaskService,
) -> None:
    """Test error when student not found by telegram_id."""
    with pytest.raises(StudentNotFoundError):
        await service.get_student_tasks_by_telegram_id(99999)


@pytest.mark.asyncio
async def test_create_and_get_task_integration(
    service: StudentTaskService,
    student: Student,
) -> None:
    """Test creating and retrieving task."""
    deadline = date.today() + timedelta(days=5)
    created_task = await service.create_task(
        student_id=student.id,
        title="Integration test task",
        description="Test description",
        deadline=deadline,
    )

    tasks = await service.get_student_tasks(student.id)

    assert len(tasks) == 1
    assert tasks[0].id == created_task.id
    assert tasks[0].title == "Integration test task"
    assert tasks[0].description == "Test description"
    assert tasks[0].deadline == deadline
    assert tasks[0].status == "open"
