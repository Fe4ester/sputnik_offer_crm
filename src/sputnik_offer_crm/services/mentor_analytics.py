"""Service for mentor analytics and export."""

import csv
import io
from dataclasses import dataclass
from datetime import date

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sputnik_offer_crm.models import (
    Direction,
    Stage,
    Student,
    StudentProgress,
    StudentStageProgress,
)


@dataclass
class DirectionSummary:
    """Summary statistics for a direction."""

    direction_code: str
    direction_name: str
    total_students: int
    active_students: int
    paused_students: int
    dropped_students: int
    completed_with_offer: int


@dataclass
class StageProgress:
    """Student count by stage."""

    direction_code: str
    direction_name: str
    stage_number: int
    stage_title: str
    students_count: int


@dataclass
class DeadlineInfo:
    """Deadline information."""

    student_name: str
    direction_name: str
    stage_title: str
    deadline_date: date
    is_overdue: bool


class MentorAnalyticsService:
    """Service for mentor analytics and reporting."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_direction_summaries(self) -> list[DirectionSummary]:
        """
        Get summary statistics for all directions.

        Returns:
            List of DirectionSummary with aggregated data
        """
        result = await self.session.execute(select(Direction).order_by(Direction.name))
        directions = result.scalars().all()

        summaries = []
        for direction in directions:
            # Get all students in this direction
            students_result = await self.session.execute(
                select(Student)
                .join(StudentProgress, StudentProgress.student_id == Student.id)
                .where(StudentProgress.direction_id == direction.id)
            )
            students = students_result.scalars().all()

            total = len(students)
            active = sum(1 for s in students if s.is_active and not s.is_paused)
            paused = sum(1 for s in students if s.is_active and s.is_paused)
            dropped = sum(1 for s in students if not s.is_active)
            # Completed students are those who are active AND have offer
            completed = sum(
                1
                for s in students
                if s.is_active and not s.is_paused and s.offer_company is not None
            )

            summaries.append(
                DirectionSummary(
                    direction_code=direction.code,
                    direction_name=direction.name,
                    total_students=total,
                    active_students=active,
                    paused_students=paused,
                    dropped_students=dropped,
                    completed_with_offer=completed,
                )
            )

        return summaries

    async def get_stage_progress(self) -> list[StageProgress]:
        """
        Get student count by stage for all directions.

        Returns:
            List of StageProgress with student counts per stage
        """
        # Get all directions and stages
        result = await self.session.execute(
            select(Direction, Stage)
            .join(Stage, Stage.direction_id == Direction.id)
            .order_by(Direction.name, Stage.stage_number)
        )
        direction_stages = result.all()

        progress_list = []
        for direction, stage in direction_stages:
            # Count active students on this stage
            count_result = await self.session.execute(
                select(func.count(StudentProgress.id))
                .join(Student, Student.id == StudentProgress.student_id)
                .where(
                    and_(
                        StudentProgress.current_stage_id == stage.id,
                        Student.is_active == True,  # noqa: E712
                    )
                )
            )
            count = count_result.scalar() or 0

            progress_list.append(
                StageProgress(
                    direction_code=direction.code,
                    direction_name=direction.name,
                    stage_number=stage.stage_number,
                    stage_title=stage.title,
                    students_count=count,
                )
            )

        return progress_list

    async def get_all_deadlines(self) -> list[DeadlineInfo]:
        """
        Get all active deadlines with overdue status.

        Returns:
            List of DeadlineInfo for active students
        """
        today = date.today()

        result = await self.session.execute(
            select(Student, Direction, Stage, StudentStageProgress)
            .join(StudentProgress, StudentProgress.student_id == Student.id)
            .join(Direction, Direction.id == StudentProgress.direction_id)
            .join(Stage, Stage.id == StudentProgress.current_stage_id)
            .join(
                StudentStageProgress,
                and_(
                    StudentStageProgress.student_id == Student.id,
                    StudentStageProgress.stage_id == Stage.id,
                ),
            )
            .where(
                and_(
                    Student.is_active == True,  # noqa: E712
                    StudentStageProgress.planned_deadline.isnot(None),
                )
            )
            .order_by(StudentStageProgress.planned_deadline)
        )

        deadlines = []
        for student, direction, stage, stage_progress in result:
            deadline_date = stage_progress.planned_deadline
            is_overdue = deadline_date < today

            student_name = f"{student.first_name}"
            if student.last_name:
                student_name += f" {student.last_name}"

            deadlines.append(
                DeadlineInfo(
                    student_name=student_name,
                    direction_name=direction.name,
                    stage_title=stage.title,
                    deadline_date=deadline_date,
                    is_overdue=is_overdue,
                )
            )

        return deadlines

    async def export_to_csv(self) -> tuple[str, str, str]:
        """
        Export all analytics data to CSV format.

        Returns:
            Tuple of (directions_csv, stages_csv, deadlines_csv)
        """
        # Export direction summaries
        directions = await self.get_direction_summaries()
        directions_output = io.StringIO()
        directions_writer = csv.writer(directions_output)
        directions_writer.writerow([
            "Направление (код)",
            "Направление (название)",
            "Всего учеников",
            "Активных",
            "На паузе",
            "Отчислено",
            "Завершили с оффером",
        ])
        for d in directions:
            directions_writer.writerow([
                d.direction_code,
                d.direction_name,
                d.total_students,
                d.active_students,
                d.paused_students,
                d.dropped_students,
                d.completed_with_offer,
            ])
        directions_csv = directions_output.getvalue()

        # Export stage progress
        stages = await self.get_stage_progress()
        stages_output = io.StringIO()
        stages_writer = csv.writer(stages_output)
        stages_writer.writerow([
            "Направление (код)",
            "Направление (название)",
            "Номер этапа",
            "Название этапа",
            "Учеников на этапе",
        ])
        for s in stages:
            stages_writer.writerow([
                s.direction_code,
                s.direction_name,
                s.stage_number,
                s.stage_title,
                s.students_count,
            ])
        stages_csv = stages_output.getvalue()

        # Export deadlines
        deadlines = await self.get_all_deadlines()
        deadlines_output = io.StringIO()
        deadlines_writer = csv.writer(deadlines_output)
        deadlines_writer.writerow([
            "Ученик",
            "Направление",
            "Этап",
            "Дедлайн",
            "Просрочен",
        ])
        for d in deadlines:
            deadlines_writer.writerow([
                d.student_name,
                d.direction_name,
                d.stage_title,
                d.deadline_date.strftime("%Y-%m-%d"),
                "Да" if d.is_overdue else "Нет",
            ])
        deadlines_csv = deadlines_output.getvalue()

        return directions_csv, stages_csv, deadlines_csv
