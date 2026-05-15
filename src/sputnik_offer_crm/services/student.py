"""Student service."""

from datetime import date, datetime, timezone
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sputnik_offer_crm.models import (
    Direction,
    Stage,
    Student,
    StudentProgress,
    StudentStageProgress,
    StudentTask,
)


class StudentProgressInfo(NamedTuple):
    """Student progress information."""

    student: Student
    direction: Direction
    current_stage: Stage
    progress: StudentProgress


class DeadlineInfo(NamedTuple):
    """Deadline information."""

    deadline_type: str  # "stage" or "task"
    title: str
    deadline_date: date
    is_overdue: bool
    stage_name: str | None = None  # For stage deadlines
    task_id: int | None = None  # For task deadlines


class StageOverviewInfo(NamedTuple):
    """Stage overview information for student."""

    stage: Stage
    status: str  # "completed", "current", "upcoming"
    deadline: date | None
    is_overdue: bool


class StudentService:
    """Service for student operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_student_progress(self, telegram_id: int) -> StudentProgressInfo | None:
        """
        Get student progress information.

        Returns:
            StudentProgressInfo or None if student not found
        """
        # Get student
        result = await self.session.execute(
            select(Student).where(Student.telegram_id == telegram_id)
        )
        student = result.scalar_one_or_none()

        if not student:
            return None

        # Get student progress
        result = await self.session.execute(
            select(StudentProgress).where(StudentProgress.student_id == student.id)
        )
        progress = result.scalar_one_or_none()

        if not progress:
            return None

        # Get direction
        result = await self.session.execute(
            select(Direction).where(Direction.id == progress.direction_id)
        )
        direction = result.scalar_one()

        # Get current stage
        result = await self.session.execute(
            select(Stage).where(Stage.id == progress.current_stage_id)
        )
        current_stage = result.scalar_one()

        return StudentProgressInfo(
            student=student,
            direction=direction,
            current_stage=current_stage,
            progress=progress,
        )

    async def get_student_deadlines(self, telegram_id: int) -> list[DeadlineInfo]:
        """
        Get student deadlines from stage progress and tasks.

        Returns:
            List of DeadlineInfo sorted by deadline date
        """
        # Get student
        result = await self.session.execute(
            select(Student).where(Student.telegram_id == telegram_id)
        )
        student = result.scalar_one_or_none()

        if not student:
            return []

        deadlines: list[DeadlineInfo] = []
        today = date.today()

        # Get stage deadlines (from db-schema.txt stages table)
        result = await self.session.execute(
            select(StudentStageProgress, Stage)
            .join(Stage, StudentStageProgress.stage_id == Stage.id)
            .where(
                StudentStageProgress.student_id == student.id,
                StudentStageProgress.planned_deadline.is_not(None),
            )
        )
        stage_progress_rows = result.all()

        for stage_progress, stage in stage_progress_rows:
            if stage_progress.planned_deadline:
                deadlines.append(
                    DeadlineInfo(
                        deadline_type="stage",
                        title=f"Этап: {stage.title}",
                        deadline_date=stage_progress.planned_deadline,
                        is_overdue=stage_progress.planned_deadline < today,
                        stage_name=stage.title,
                    )
                )

        # Get task deadlines
        result = await self.session.execute(
            select(StudentTask).where(
                StudentTask.student_id == student.id,
                StudentTask.deadline.is_not(None),
                StudentTask.completed_at.is_(None),  # Only incomplete tasks
            )
        )
        tasks = result.scalars().all()

        for task in tasks:
            if task.deadline:
                deadlines.append(
                    DeadlineInfo(
                        deadline_type="task",
                        title=task.title,
                        deadline_date=task.deadline,
                        is_overdue=task.deadline < today,
                        task_id=task.id,
                    )
                )

        # Sort by deadline date
        deadlines.sort(key=lambda d: d.deadline_date)

        return deadlines

    async def get_stages_overview(self, telegram_id: int) -> list[StageOverviewInfo]:
        """
        Get overview of all stages in student's direction with their statuses.

        Returns:
            List of StageOverviewInfo ordered by stage order
        """
        # Get student progress
        progress_info = await self.get_student_progress(telegram_id)
        if not progress_info:
            return []

        student = progress_info.student
        direction = progress_info.direction
        current_stage_id = progress_info.progress.current_stage_id

        # Get all stages for this direction
        result = await self.session.execute(
            select(Stage)
            .where(Stage.direction_id == direction.id)
            .order_by(Stage.stage_number)
        )
        stages = result.scalars().all()

        # Get all stage progress records for this student
        result = await self.session.execute(
            select(StudentStageProgress)
            .where(StudentStageProgress.student_id == student.id)
        )
        stage_progress_map = {sp.stage_id: sp for sp in result.scalars().all()}

        # Build overview
        overview: list[StageOverviewInfo] = []
        today = date.today()
        found_current = False

        for stage in stages:
            stage_progress = stage_progress_map.get(stage.id)

            # Determine status
            if stage_progress and stage_progress.completed_at:
                status = "completed"
            elif stage.id == current_stage_id:
                status = "current"
                found_current = True
            elif not found_current:
                # Before current stage but not completed - shouldn't happen normally
                status = "completed"
            else:
                status = "upcoming"

            # Get deadline
            deadline = stage_progress.planned_deadline if stage_progress else None
            is_overdue = deadline < today if deadline else False

            overview.append(
                StageOverviewInfo(
                    stage=stage,
                    status=status,
                    deadline=deadline,
                    is_overdue=is_overdue,
                )
            )

        return overview

    async def get_completed_stages_count(self, telegram_id: int) -> tuple[int, int]:
        """
        Get count of completed stages and total stages.

        Returns:
            Tuple of (completed_count, total_count)
        """
        # Get student progress
        progress_info = await self.get_student_progress(telegram_id)
        if not progress_info:
            return (0, 0)

        student = progress_info.student
        direction = progress_info.direction

        # Get total stages count
        result = await self.session.execute(
            select(Stage).where(Stage.direction_id == direction.id)
        )
        total_count = len(result.scalars().all())

        # Get completed stages count
        result = await self.session.execute(
            select(StudentStageProgress)
            .where(
                StudentStageProgress.student_id == student.id,
                StudentStageProgress.completed_at.is_not(None),
            )
        )
        completed_count = len(result.scalars().all())

        return (completed_count, total_count)
