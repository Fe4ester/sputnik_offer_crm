"""Mentor student view service."""

from datetime import date
from typing import NamedTuple

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from sputnik_offer_crm.models import (
    Direction,
    Stage,
    Student,
    StudentProgress,
    WeeklyReport,
)
from sputnik_offer_crm.services.student import DeadlineInfo, StudentService


class StudentSearchResult(NamedTuple):
    """Student search result."""

    student: Student
    direction_name: str | None


class StudentCardInfo(NamedTuple):
    """Student card information for mentor."""

    student: Student
    direction: Direction
    current_stage: Stage
    progress: StudentProgress
    deadlines: list[DeadlineInfo]
    recent_reports: list[WeeklyReport]


class MentorStudentService:
    """Service for mentor student view operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def search_students(self, query: str) -> list[StudentSearchResult]:
        """
        Search students by username, name, or telegram_id.

        Args:
            query: search query (username, name, or telegram_id)

        Returns:
            list of StudentSearchResult
        """
        query = query.strip()

        # Try to parse as telegram_id (numeric)
        telegram_id = None
        try:
            telegram_id = int(query)
        except ValueError:
            pass

        # Build search conditions
        conditions = []

        # Search by username (with or without @)
        username_query = query.lstrip("@")
        conditions.append(Student.username.ilike(f"%{username_query}%"))

        # Search by name
        conditions.append(Student.first_name.ilike(f"%{query}%"))
        conditions.append(Student.last_name.ilike(f"%{query}%"))

        # Search by telegram_id if numeric
        if telegram_id:
            conditions.append(Student.telegram_id == telegram_id)

        # Execute search
        result = await self.session.execute(
            select(Student, Direction)
            .outerjoin(StudentProgress, StudentProgress.student_id == Student.id)
            .outerjoin(Direction, Direction.id == StudentProgress.direction_id)
            .where(or_(*conditions))
            .order_by(Student.created_at.desc())
            .limit(10)  # Limit results
        )
        rows = result.all()

        # Build results
        search_results = []
        for student, direction in rows:
            search_results.append(
                StudentSearchResult(
                    student=student,
                    direction_name=direction.name if direction else None,
                )
            )

        return search_results

    async def get_student_card(self, student_id: int) -> StudentCardInfo | None:
        """
        Get student card information for mentor.

        Args:
            student_id: student ID

        Returns:
            StudentCardInfo or None if not found
        """
        # Get student
        result = await self.session.execute(
            select(Student).where(Student.id == student_id)
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

        # Get deadlines using StudentService
        student_service = StudentService(self.session)
        deadlines = await student_service.get_student_deadlines(student.telegram_id)

        # Get recent weekly reports (last 3)
        result = await self.session.execute(
            select(WeeklyReport)
            .where(WeeklyReport.student_id == student.id)
            .order_by(WeeklyReport.week_start_date.desc())
            .limit(3)
        )
        recent_reports = list(result.scalars().all())

        return StudentCardInfo(
            student=student,
            direction=direction,
            current_stage=current_stage,
            progress=progress,
            deadlines=deadlines,
            recent_reports=recent_reports,
        )
