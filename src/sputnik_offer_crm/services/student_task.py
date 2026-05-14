"""Student task management service."""

from datetime import date
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sputnik_offer_crm.models import Student, StudentTask, TaskStatus


class TaskInfo(NamedTuple):
    """Task information for display."""

    id: int
    title: str
    description: str | None
    deadline: date | None
    status: str
    mentor_task: str | None


class StudentTaskError(Exception):
    """Base error for student task operations."""


class StudentNotFoundError(StudentTaskError):
    """Student not found."""


class TaskNotFoundError(StudentTaskError):
    """Task not found."""


class StudentTaskService:
    """Service for student task operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_task(
        self,
        student_id: int,
        title: str,
        description: str | None = None,
        deadline: date | None = None,
        mentor_task: str | None = None,
    ) -> StudentTask:
        """
        Create new task for student.

        Args:
            student_id: student ID
            title: task title
            description: optional task description
            deadline: optional deadline date
            mentor_task: optional mentor task reference

        Returns:
            Created task

        Raises:
            StudentNotFoundError: if student not found
        """
        # Verify student exists
        result = await self.session.execute(
            select(Student).where(Student.id == student_id)
        )
        student = result.scalar_one_or_none()

        if not student:
            raise StudentNotFoundError(f"Student {student_id} not found")

        # Create task
        task = StudentTask(
            student_id=student_id,
            title=title.strip(),
            description=description.strip() if description else None,
            deadline=deadline,
            mentor_task=mentor_task.strip() if mentor_task else None,
            status=TaskStatus.OPEN.value,
        )
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)

        return task

    async def get_student_tasks(self, student_id: int) -> list[TaskInfo]:
        """
        Get all tasks for student.

        Args:
            student_id: student ID

        Returns:
            List of TaskInfo ordered by created_at desc

        Raises:
            StudentNotFoundError: if student not found
        """
        # Verify student exists
        result = await self.session.execute(
            select(Student).where(Student.id == student_id)
        )
        student = result.scalar_one_or_none()

        if not student:
            raise StudentNotFoundError(f"Student {student_id} not found")

        # Get tasks
        result = await self.session.execute(
            select(StudentTask)
            .where(StudentTask.student_id == student_id)
            .order_by(StudentTask.created_at.desc())
        )
        tasks = result.scalars().all()

        return [
            TaskInfo(
                id=task.id,
                title=task.title,
                description=task.description,
                deadline=task.deadline,
                status=task.status,
                mentor_task=task.mentor_task,
            )
            for task in tasks
        ]

    async def get_student_tasks_by_telegram_id(
        self, telegram_id: int
    ) -> list[TaskInfo]:
        """
        Get all tasks for student by telegram_id.

        Args:
            telegram_id: student telegram ID

        Returns:
            List of TaskInfo ordered by created_at desc

        Raises:
            StudentNotFoundError: if student not found
        """
        # Get student by telegram_id
        result = await self.session.execute(
            select(Student).where(Student.telegram_id == telegram_id)
        )
        student = result.scalar_one_or_none()

        if not student:
            raise StudentNotFoundError(f"Student with telegram_id {telegram_id} not found")

        return await self.get_student_tasks(student.id)
