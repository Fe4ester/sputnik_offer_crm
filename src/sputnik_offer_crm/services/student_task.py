"""Student task management service."""

from datetime import date, datetime, timezone
from typing import NamedTuple

from sqlalchemy import and_, select
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


class TaskAlreadyCompletedError(StudentTaskError):
    """Task is already completed."""


class TaskAlreadyCancelledError(StudentTaskError):
    """Task is already cancelled."""


class InvalidTaskTransitionError(StudentTaskError):
    """Invalid task status transition."""


class StudentTaskService:
    """Service for student task operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def sync_task_statuses(self, student_id: int | None = None) -> int:
        """Sync task statuses between open/overdue based on deadline."""
        today = date.today()
        filters = [
            StudentTask.deadline.is_not(None),
            StudentTask.status.in_([TaskStatus.OPEN.value, TaskStatus.OVERDUE.value]),
        ]
        if student_id is not None:
            filters.append(StudentTask.student_id == student_id)

        result = await self.session.execute(
            select(StudentTask).where(and_(*filters))
        )
        tasks = result.scalars().all()

        changed = 0
        for task in tasks:
            if not task.deadline:
                continue
            if task.status == TaskStatus.OPEN.value and task.deadline < today:
                task.status = TaskStatus.OVERDUE.value
                changed += 1
            elif task.status == TaskStatus.OVERDUE.value and task.deadline >= today:
                task.status = TaskStatus.OPEN.value
                changed += 1

        if changed:
            await self.session.commit()

        return changed

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

        await self.sync_task_statuses(student_id=student_id)

        # Get tasks
        result = await self.session.execute(
            select(StudentTask)
            .where(StudentTask.student_id == student_id)
            .order_by(StudentTask.created_at.desc(), StudentTask.id.desc())
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

    async def complete_task(self, task_id: int, student_telegram_id: int) -> StudentTask:
        """
        Mark task as completed by student.

        Args:
            task_id: task ID
            student_telegram_id: student telegram ID (for verification)

        Returns:
            Updated task

        Raises:
            TaskNotFoundError: if task not found
            InvalidTaskTransitionError: if task cannot be completed
        """
        # Get task
        result = await self.session.execute(
            select(StudentTask).where(StudentTask.id == task_id)
        )
        task = result.scalar_one_or_none()

        if not task:
            raise TaskNotFoundError(f"Task {task_id} not found")

        # Verify task belongs to student
        result = await self.session.execute(
            select(Student).where(
                Student.id == task.student_id,
                Student.telegram_id == student_telegram_id,
            )
        )
        student = result.scalar_one_or_none()

        if not student:
            raise TaskNotFoundError(f"Task {task_id} not found for this student")

        # Check current status
        if task.status == TaskStatus.DONE.value:
            raise TaskAlreadyCompletedError(f"Task {task_id} is already completed")

        if task.status == TaskStatus.CANCELLED.value:
            raise InvalidTaskTransitionError(
                f"Cannot complete cancelled task {task_id}"
            )

        # Mark as done
        task.status = TaskStatus.DONE.value
        task.completed_at = datetime.now(timezone.utc)

        await self.session.commit()
        await self.session.refresh(task)

        return task

    async def cancel_task(self, task_id: int) -> StudentTask:
        """
        Cancel task (mentor action).

        Args:
            task_id: task ID

        Returns:
            Updated task

        Raises:
            TaskNotFoundError: if task not found
            InvalidTaskTransitionError: if task cannot be cancelled
        """
        # Get task
        result = await self.session.execute(
            select(StudentTask).where(StudentTask.id == task_id)
        )
        task = result.scalar_one_or_none()

        if not task:
            raise TaskNotFoundError(f"Task {task_id} not found")

        # Check current status
        if task.status == TaskStatus.CANCELLED.value:
            raise TaskAlreadyCancelledError(f"Task {task_id} is already cancelled")

        if task.status == TaskStatus.DONE.value:
            raise InvalidTaskTransitionError(
                f"Cannot cancel completed task {task_id}"
            )

        # Mark as cancelled
        task.status = TaskStatus.CANCELLED.value

        await self.session.commit()
        await self.session.refresh(task)

        return task

    async def get_task(self, task_id: int) -> StudentTask | None:
        """
        Get task by ID.

        Args:
            task_id: task ID

        Returns:
            Task or None if not found
        """
        result = await self.session.execute(
            select(StudentTask).where(StudentTask.id == task_id)
        )
        return result.scalar_one_or_none()
