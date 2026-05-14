"""Notification service for reminders and alerts."""

from datetime import date, datetime, timedelta
from typing import NamedTuple

import pytz
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from sputnik_offer_crm.models import (
    NotificationLog,
    Student,
    StudentProgress,
    StudentStageProgress,
    WeeklyReport,
)
from sputnik_offer_crm.services.weekly_report import WeeklyReportService


class NotificationRecipient(NamedTuple):
    """Notification recipient info."""

    student_id: int
    telegram_id: int
    first_name: str
    last_name: str | None
    timezone: str


class WeeklyReportReminder(NamedTuple):
    """Weekly report reminder notification."""

    recipient: NotificationRecipient
    week_start_date: date
    message: str


class DeadlineReminder(NamedTuple):
    """Deadline reminder notification."""

    recipient: NotificationRecipient
    deadline_date: date
    deadline_title: str
    days_until: int
    is_overdue: bool
    message: str


class NotificationService:
    """Service for notification and reminder logic."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _log_notification(
        self,
        student_id: int,
        notification_type: str,
        notification_key: str,
        message: str,
    ) -> None:
        """
        Log sent notification for deduplication.

        Args:
            student_id: student ID
            notification_type: type of notification (e.g., "weekly_report_reminder")
            notification_key: unique key for this notification (e.g., "2026-05-12")
            message: notification message
        """
        now = datetime.now(pytz.UTC)
        log_entry = NotificationLog(
            student_id=student_id,
            notification_type=notification_type,
            notification_key=notification_key,
            sent_date=now,
            message=message,
        )
        self.session.add(log_entry)
        await self.session.flush()

    async def _was_notification_sent_today(
        self,
        student_id: int,
        notification_type: str,
        notification_key: str,
    ) -> bool:
        """
        Check if notification was already sent today.

        Args:
            student_id: student ID
            notification_type: type of notification
            notification_key: unique key for this notification

        Returns:
            True if notification was sent today, False otherwise
        """
        now = datetime.now(pytz.UTC)
        today_start = datetime(now.year, now.month, now.day, tzinfo=pytz.UTC)

        result = await self.session.execute(
            select(NotificationLog).where(
                and_(
                    NotificationLog.student_id == student_id,
                    NotificationLog.notification_type == notification_type,
                    NotificationLog.notification_key == notification_key,
                    NotificationLog.sent_date >= today_start,
                )
            )
        )
        return result.scalar_one_or_none() is not None

    async def get_weekly_report_reminders(self) -> list[WeeklyReportReminder]:
        """
        Get list of students who need weekly report reminder.

        Returns:
            List of WeeklyReportReminder for students who:
            - are active (not dropped)
            - are not paused
            - have not submitted report for current week
            - have not received reminder today
        """
        # Get all active, non-paused students
        result = await self.session.execute(
            select(Student).where(
                and_(
                    Student.is_active == True,  # noqa: E712
                    Student.is_paused == False,  # noqa: E712
                )
            )
        )
        students = result.scalars().all()

        reminders = []
        weekly_service = WeeklyReportService(self.session)

        for student in students:
            # Get current week start in student's timezone
            now = datetime.now(pytz.UTC)
            week_start = weekly_service.get_week_start_date(now, student.timezone)

            # Check if report already submitted
            report_result = await self.session.execute(
                select(WeeklyReport).where(
                    and_(
                        WeeklyReport.student_id == student.id,
                        WeeklyReport.week_start_date == week_start,
                    )
                )
            )
            if report_result.scalar_one_or_none() is not None:
                continue

            # Check if reminder already sent today
            notification_key = week_start.isoformat()
            if await self._was_notification_sent_today(
                student.id,
                "weekly_report_reminder",
                notification_key,
            ):
                continue

            # Create reminder
            recipient = NotificationRecipient(
                student_id=student.id,
                telegram_id=student.telegram_id,
                first_name=student.first_name,
                last_name=student.last_name,
                timezone=student.timezone,
            )

            message = (
                f"📝 Напоминание о еженедельном отчёте\n\n"
                f"Не забудьте отправить отчёт за текущую неделю (с {week_start.strftime('%d.%m.%Y')}).\n\n"
                f"Используйте кнопку '📝 Отправить' в меню."
            )

            reminders.append(
                WeeklyReportReminder(
                    recipient=recipient,
                    week_start_date=week_start,
                    message=message,
                )
            )

        return reminders

    async def get_deadline_reminders(
        self,
        upcoming_days: int = 3,
    ) -> list[DeadlineReminder]:
        """
        Get list of deadline reminders.

        Args:
            upcoming_days: how many days ahead to check for upcoming deadlines

        Returns:
            List of DeadlineReminder for:
            - upcoming deadlines (within upcoming_days)
            - overdue deadlines
            Only for active, non-paused students who haven't received reminder today.
        """
        # Get all active, non-paused students with progress
        result = await self.session.execute(
            select(Student, StudentProgress)
            .join(StudentProgress, StudentProgress.student_id == Student.id)
            .where(
                and_(
                    Student.is_active == True,  # noqa: E712
                    Student.is_paused == False,  # noqa: E712
                )
            )
        )
        student_progress_pairs = result.all()

        reminders = []
        now = datetime.now(pytz.UTC)
        today = now.date()

        for student, progress in student_progress_pairs:
            # Get student's current stage progress with deadline
            stage_result = await self.session.execute(
                select(StudentStageProgress).where(
                    and_(
                        StudentStageProgress.student_id == student.id,
                        StudentStageProgress.stage_id == progress.current_stage_id,
                        StudentStageProgress.planned_deadline.isnot(None),
                    )
                )
            )
            stage_progress = stage_result.scalar_one_or_none()

            if not stage_progress or not stage_progress.planned_deadline:
                continue

            deadline_date = stage_progress.planned_deadline
            days_until = (deadline_date - today).days

            # Check if deadline is upcoming or overdue
            is_overdue = days_until < 0
            is_upcoming = 0 <= days_until <= upcoming_days

            if not (is_overdue or is_upcoming):
                continue

            # Determine notification key and type
            if is_overdue:
                notification_type = "deadline_overdue"
                notification_key = f"stage_{stage_progress.stage_id}_{deadline_date.isoformat()}"
            else:
                notification_type = "deadline_upcoming"
                notification_key = f"stage_{stage_progress.stage_id}_{deadline_date.isoformat()}"

            # Check if reminder already sent today
            if await self._was_notification_sent_today(
                student.id,
                notification_type,
                notification_key,
            ):
                continue

            # Get stage title
            from sputnik_offer_crm.models import Stage

            stage_result = await self.session.execute(
                select(Stage).where(Stage.id == stage_progress.stage_id)
            )
            stage = stage_result.scalar_one()

            # Create reminder
            recipient = NotificationRecipient(
                student_id=student.id,
                telegram_id=student.telegram_id,
                first_name=student.first_name,
                last_name=student.last_name,
                timezone=student.timezone,
            )

            if is_overdue:
                message = (
                    f"⚠️ Дедлайн просрочен\n\n"
                    f"📍 Этап: {stage.title}\n"
                    f"📅 Дедлайн был: {deadline_date.strftime('%d.%m.%Y')}\n"
                    f"⏰ Просрочено на {abs(days_until)} дн.\n\n"
                    f"Обратитесь к ментору для уточнения ситуации."
                )
            else:
                message = (
                    f"📅 Напоминание о дедлайне\n\n"
                    f"📍 Этап: {stage.title}\n"
                    f"📅 Дедлайн: {deadline_date.strftime('%d.%m.%Y')}\n"
                    f"⏰ Осталось {days_until} дн.\n\n"
                    f"Не забудьте завершить этап вовремя!"
                )

            reminders.append(
                DeadlineReminder(
                    recipient=recipient,
                    deadline_date=deadline_date,
                    deadline_title=stage.title,
                    days_until=days_until,
                    is_overdue=is_overdue,
                    message=message,
                )
            )

        return reminders

    async def mark_weekly_report_reminder_sent(
        self,
        student_id: int,
        week_start_date: date,
        message: str,
    ) -> None:
        """Mark weekly report reminder as sent."""
        await self._log_notification(
            student_id=student_id,
            notification_type="weekly_report_reminder",
            notification_key=week_start_date.isoformat(),
            message=message,
        )

    async def mark_deadline_reminder_sent(
        self,
        student_id: int,
        stage_id: int,
        deadline_date: date,
        is_overdue: bool,
        message: str,
    ) -> None:
        """Mark deadline reminder as sent."""
        notification_type = "deadline_overdue" if is_overdue else "deadline_upcoming"
        notification_key = f"stage_{stage_id}_{deadline_date.isoformat()}"

        await self._log_notification(
            student_id=student_id,
            notification_type=notification_type,
            notification_key=notification_key,
            message=message,
        )
