"""Tests for notification job."""

from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytz

from sputnik_offer_crm.jobs.notification_job import (
    run_notification_job,
    send_deadline_reminders,
    send_task_reminders,
    send_weekly_report_reminders,
)
from sputnik_offer_crm.models import (
    Direction,
    Stage,
    Student,
    StudentProgress,
    StudentStageProgress,
)
from sputnik_offer_crm.services import NotificationRecipient


@pytest.fixture
async def student_with_progress(db_session, direction, stage):
    """Create student with progress."""
    student = Student(
        telegram_id=123456789,
        first_name="Test",
        last_name="Student",
        username="teststudent",
        timezone="Europe/Moscow",
        is_active=True,
        is_paused=False,
    )
    db_session.add(student)
    await db_session.flush()

    progress = StudentProgress(
        student_id=student.id,
        direction_id=direction.id,
        current_stage_id=stage.id,
        started_at=datetime.now(pytz.UTC),
    )
    db_session.add(progress)
    await db_session.commit()
    await db_session.refresh(student)
    return student


@pytest.fixture
async def direction(db_session):
    """Create test direction."""
    direction = Direction(code="test", name="Test Direction", is_active=True)
    db_session.add(direction)
    await db_session.commit()
    await db_session.refresh(direction)
    return direction


@pytest.fixture
async def stage(db_session, direction):
    """Create test stage."""
    stage = Stage(
        direction_id=direction.id,
        stage_number=1,
        title="Test Stage",
        planned_duration_days=14,
        is_active=True,
    )
    db_session.add(stage)
    await db_session.commit()
    await db_session.refresh(stage)
    return stage


@pytest.mark.asyncio
async def test_send_weekly_report_reminders_empty():
    """Test sending weekly report reminders when none exist."""
    with patch("sputnik_offer_crm.jobs.notification_job.get_session") as mock_session:
        mock_db = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_db

        with patch(
            "sputnik_offer_crm.jobs.notification_job.NotificationService"
        ) as mock_service_class:
            mock_service = AsyncMock()
            mock_service.get_weekly_report_reminders.return_value = []
            mock_service_class.return_value = mock_service

            sent, failed = await send_weekly_report_reminders()

            assert sent == 0
            assert failed == 0
            mock_service.get_weekly_report_reminders.assert_called_once()


@pytest.mark.asyncio
async def test_send_weekly_report_reminders_with_data():
    """Test sending weekly report reminders with data."""
    with patch("sputnik_offer_crm.jobs.notification_job.get_session") as mock_session:
        mock_db = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_db

        with patch(
            "sputnik_offer_crm.jobs.notification_job.NotificationService"
        ) as mock_service_class:
            mock_service = AsyncMock()

            # Create mock reminder
            recipient = NotificationRecipient(
                student_id=1,
                telegram_id=123456789,
                first_name="Test",
                last_name="Student",
                timezone="Europe/Moscow",
            )

            from sputnik_offer_crm.services import WeeklyReportReminder

            reminder = WeeklyReportReminder(
                recipient=recipient,
                week_start_date=date.today(),
                message="Test message",
            )

            mock_service.get_weekly_report_reminders.return_value = [reminder]
            mock_service_class.return_value = mock_service

            with patch("aiogram.Bot") as mock_bot_class:
                mock_bot = AsyncMock()
                mock_bot_class.return_value = mock_bot

                sent, failed = await send_weekly_report_reminders()

                assert sent == 1
                assert failed == 0
                mock_bot.send_message.assert_called_once()
                mock_service.mark_weekly_report_reminder_sent.assert_called_once()


@pytest.mark.asyncio
async def test_send_deadline_reminders_empty():
    """Test sending deadline reminders when none exist."""
    with patch("sputnik_offer_crm.jobs.notification_job.get_session") as mock_session:
        mock_db = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_db

        with patch(
            "sputnik_offer_crm.jobs.notification_job.NotificationService"
        ) as mock_service_class:
            mock_service = AsyncMock()
            mock_service.get_deadline_reminders.return_value = []
            mock_service_class.return_value = mock_service

            sent, failed = await send_deadline_reminders()

            assert sent == 0
            assert failed == 0
            mock_service.get_deadline_reminders.assert_called_once()


@pytest.mark.asyncio
async def test_send_deadline_reminders_with_data():
    """Test sending deadline reminders with data."""
    with patch("sputnik_offer_crm.jobs.notification_job.get_session") as mock_session:
        mock_db = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_db

        with patch(
            "sputnik_offer_crm.jobs.notification_job.NotificationService"
        ) as mock_service_class:
            mock_service = AsyncMock()

            # Create mock reminder
            recipient = NotificationRecipient(
                student_id=1,
                telegram_id=123456789,
                first_name="Test",
                last_name="Student",
                timezone="Europe/Moscow",
            )

            from sputnik_offer_crm.services import DeadlineReminder

            reminder = DeadlineReminder(
                recipient=recipient,
                stage_id=1,
                deadline_date=date.today() + timedelta(days=2),
                deadline_title="Test Stage",
                days_until=2,
                is_overdue=False,
                message="Test deadline message",
            )

            mock_service.get_deadline_reminders.return_value = [reminder]
            mock_service_class.return_value = mock_service

            with patch("aiogram.Bot") as mock_bot_class:
                mock_bot = AsyncMock()
                mock_bot_class.return_value = mock_bot

                sent, failed = await send_deadline_reminders()

                assert sent == 1
                assert failed == 0
                mock_bot.send_message.assert_called_once()
                mock_service.mark_deadline_reminder_sent.assert_called_once()


@pytest.mark.asyncio
async def test_run_notification_job_success():
    """Test running notification job successfully."""
    with patch(
        "sputnik_offer_crm.jobs.notification_job.send_weekly_report_reminders"
    ) as mock_weekly:
        mock_weekly.return_value = (2, 0)

        with patch(
            "sputnik_offer_crm.jobs.notification_job.send_deadline_reminders"
        ) as mock_deadline:
            mock_deadline.return_value = (3, 0)

            with patch(
                "sputnik_offer_crm.jobs.notification_job.send_task_reminders"
            ) as mock_task:
                mock_task.return_value = (1, 0)

                exit_code = await run_notification_job()

                assert exit_code == 0
                mock_weekly.assert_called_once()
                mock_deadline.assert_called_once()
                mock_task.assert_called_once()


@pytest.mark.asyncio
async def test_run_notification_job_with_failures():
    """Test running notification job with some failures."""
    with patch(
        "sputnik_offer_crm.jobs.notification_job.send_weekly_report_reminders"
    ) as mock_weekly:
        mock_weekly.return_value = (2, 1)

        with patch(
            "sputnik_offer_crm.jobs.notification_job.send_deadline_reminders"
        ) as mock_deadline:
            mock_deadline.return_value = (3, 2)

            with patch(
                "sputnik_offer_crm.jobs.notification_job.send_task_reminders"
            ) as mock_task:
                mock_task.return_value = (1, 0)

                exit_code = await run_notification_job()

                assert exit_code == 1  # Non-zero because of failures
                mock_weekly.assert_called_once()
                mock_deadline.assert_called_once()
                mock_task.assert_called_once()


@pytest.mark.asyncio
async def test_run_notification_job_exception():
    """Test running notification job with exception."""
    with patch(
        "sputnik_offer_crm.jobs.notification_job.send_weekly_report_reminders"
    ) as mock_weekly:
        mock_weekly.side_effect = Exception("Test error")

        exit_code = await run_notification_job()

        assert exit_code == 1


@pytest.mark.asyncio
async def test_send_task_reminders_empty():
    """Test sending task reminders when none exist."""
    with patch("sputnik_offer_crm.jobs.notification_job.get_session") as mock_session:
        mock_db = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_db

        with patch(
            "sputnik_offer_crm.jobs.notification_job.NotificationService"
        ) as mock_service_class:
            mock_service = AsyncMock()
            mock_service.get_task_reminders.return_value = []
            mock_service_class.return_value = mock_service

            sent, failed = await send_task_reminders()

            assert sent == 0
            assert failed == 0
            mock_service.get_task_reminders.assert_called_once()


@pytest.mark.asyncio
async def test_send_task_reminders_with_data():
    """Test sending task reminders with data."""
    with patch("sputnik_offer_crm.jobs.notification_job.get_session") as mock_session:
        mock_db = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_db

        with patch(
            "sputnik_offer_crm.jobs.notification_job.NotificationService"
        ) as mock_service_class:
            mock_service = AsyncMock()

            # Create mock reminder
            recipient = NotificationRecipient(
                student_id=1,
                telegram_id=123456789,
                first_name="Test",
                last_name="Student",
                timezone="Europe/Moscow",
            )

            from sputnik_offer_crm.services import TaskReminder

            reminder = TaskReminder(
                recipient=recipient,
                task_id=1,
                task_title="Test Task",
                deadline_date=date.today() + timedelta(days=2),
                days_until=2,
                is_overdue=False,
                message="Test task message",
            )

            mock_service.get_task_reminders.return_value = [reminder]
            mock_service_class.return_value = mock_service

            with patch("aiogram.Bot") as mock_bot_class:
                mock_bot = AsyncMock()
                mock_bot_class.return_value = mock_bot

                sent, failed = await send_task_reminders()

                assert sent == 1
                assert failed == 0
                mock_bot.send_message.assert_called_once()
                mock_service.mark_task_reminder_sent.assert_called_once()


@pytest.mark.asyncio
async def test_run_notification_job_with_tasks():
    """Test running notification job with task reminders."""
    with patch(
        "sputnik_offer_crm.jobs.notification_job.send_weekly_report_reminders"
    ) as mock_weekly:
        mock_weekly.return_value = (1, 0)

        with patch(
            "sputnik_offer_crm.jobs.notification_job.send_deadline_reminders"
        ) as mock_deadline:
            mock_deadline.return_value = (2, 0)

            with patch(
                "sputnik_offer_crm.jobs.notification_job.send_task_reminders"
            ) as mock_task:
                mock_task.return_value = (3, 0)

                exit_code = await run_notification_job()

                assert exit_code == 0
                mock_weekly.assert_called_once()
                mock_deadline.assert_called_once()
                mock_task.assert_called_once()

