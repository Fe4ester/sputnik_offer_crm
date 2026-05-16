"""Notification job runner for sending reminders."""

import asyncio
import sys
from datetime import datetime

import pytz

from sputnik_offer_crm.config import get_settings
from sputnik_offer_crm.db import get_session
from sputnik_offer_crm.services import NotificationService
from sputnik_offer_crm.utils.logging import get_logger

logger = get_logger(__name__)


async def send_weekly_report_reminders() -> tuple[int, int]:
    """
    Send weekly report reminders to students.

    Returns:
        Tuple of (sent_count, failed_count)
    """
    settings = get_settings()
    sent = 0
    failed = 0

    async with get_session() as session:
        service = NotificationService(session)

        try:
            reminders = await service.get_weekly_report_reminders()
            logger.info(f"Found {len(reminders)} weekly report reminders to send")

            if not reminders:
                return 0, 0

            # Import bot here to avoid circular imports
            from aiogram import Bot
            from aiogram.client.default import DefaultBotProperties
            from aiogram.enums import ParseMode

            bot = Bot(
                token=settings.bot_token,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML),
            )

            try:
                for reminder in reminders:
                    try:
                        await bot.send_message(
                            chat_id=reminder.recipient.telegram_id,
                            text=reminder.message,
                        )

                        # Mark as sent
                        await service.mark_weekly_report_reminder_sent(
                            reminder.recipient.student_id,
                            reminder.week_start_date,
                            reminder.message,
                        )
                        await session.commit()

                        sent += 1
                        logger.info(
                            f"Sent weekly report reminder to student {reminder.recipient.student_id}"
                        )

                    except Exception as e:
                        failed += 1
                        logger.error(
                            f"Failed to send weekly report reminder to student "
                            f"{reminder.recipient.student_id}: {e}"
                        )
                        await session.rollback()

            finally:
                await bot.session.close()

        except Exception as e:
            logger.error(f"Error processing weekly report reminders: {e}")
            raise

    return sent, failed


async def send_deadline_reminders() -> tuple[int, int]:
    """
    Send deadline reminders to students.

    Returns:
        Tuple of (sent_count, failed_count)
    """
    settings = get_settings()
    sent = 0
    failed = 0

    async with get_session() as session:
        service = NotificationService(session)

        try:
            reminders = await service.get_deadline_reminders(upcoming_days=3)
            logger.info(f"Found {len(reminders)} deadline reminders to send")

            if not reminders:
                return 0, 0

            # Import bot here to avoid circular imports
            from aiogram import Bot
            from aiogram.client.default import DefaultBotProperties
            from aiogram.enums import ParseMode

            bot = Bot(
                token=settings.bot_token,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML),
            )

            try:
                for reminder in reminders:
                    try:
                        await bot.send_message(
                            chat_id=reminder.recipient.telegram_id,
                            text=reminder.message,
                        )

                        # Mark as sent
                        await service.mark_deadline_reminder_sent(
                            reminder.recipient.student_id,
                            reminder.stage_id,
                            reminder.deadline_date,
                            reminder.is_overdue,
                            reminder.message,
                        )
                        await session.commit()

                        sent += 1
                        logger.info(
                            f"Sent deadline reminder to student {reminder.recipient.student_id}"
                        )

                    except Exception as e:
                        failed += 1
                        logger.error(
                            f"Failed to send deadline reminder to student "
                            f"{reminder.recipient.student_id}: {e}"
                        )
                        await session.rollback()

            finally:
                await bot.session.close()

        except Exception as e:
            logger.error(f"Error processing deadline reminders: {e}")
            raise

    return sent, failed


async def send_task_reminders() -> tuple[int, int]:
    """
    Send task deadline reminders to students.

    Returns:
        Tuple of (sent_count, failed_count)
    """
    settings = get_settings()
    sent = 0
    failed = 0

    async with get_session() as session:
        service = NotificationService(session)

        try:
            reminders = await service.get_task_reminders(upcoming_days=3)
            logger.info(f"Found {len(reminders)} task reminders to send")

            if not reminders:
                return 0, 0

            # Import bot here to avoid circular imports
            from aiogram import Bot
            from aiogram.client.default import DefaultBotProperties
            from aiogram.enums import ParseMode

            bot = Bot(
                token=settings.bot_token,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML),
            )

            try:
                for reminder in reminders:
                    try:
                        await bot.send_message(
                            chat_id=reminder.recipient.telegram_id,
                            text=reminder.message,
                        )

                        # Mark as sent
                        await service.mark_task_reminder_sent(
                            reminder.recipient.student_id,
                            reminder.task_id,
                            reminder.deadline_date,
                            reminder.is_overdue,
                            reminder.message,
                        )
                        await session.commit()

                        sent += 1
                        logger.info(
                            f"Sent task reminder to student {reminder.recipient.student_id}"
                        )

                    except Exception as e:
                        failed += 1
                        logger.error(
                            f"Failed to send task reminder to student "
                            f"{reminder.recipient.student_id}: {e}"
                        )
                        await session.rollback()

            finally:
                await bot.session.close()

        except Exception as e:
            logger.error(f"Error processing task reminders: {e}")
            raise

    return sent, failed


async def run_notification_job() -> int:
    """
    Run notification job to send all pending reminders.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    start_time = datetime.now(pytz.UTC)
    logger.info(f"Starting notification job at {start_time.isoformat()}")

    try:
        # Send weekly report reminders
        weekly_sent, weekly_failed = await send_weekly_report_reminders()
        logger.info(
            f"Weekly report reminders: {weekly_sent} sent, {weekly_failed} failed"
        )

        # Send deadline reminders
        deadline_sent, deadline_failed = await send_deadline_reminders()
        logger.info(
            f"Deadline reminders: {deadline_sent} sent, {deadline_failed} failed"
        )

        # Send task reminders
        task_sent, task_failed = await send_task_reminders()
        logger.info(
            f"Task reminders: {task_sent} sent, {task_failed} failed"
        )

        # Calculate totals
        total_sent = weekly_sent + deadline_sent + task_sent
        total_failed = weekly_failed + deadline_failed + task_failed

        end_time = datetime.now(pytz.UTC)
        duration = (end_time - start_time).total_seconds()

        logger.info(
            f"Notification job completed in {duration:.2f}s: "
            f"{total_sent} sent, {total_failed} failed"
        )

        # Return non-zero exit code if any failures
        return 1 if total_failed > 0 else 0

    except Exception as e:
        logger.error(f"Notification job failed with error: {e}", exc_info=True)
        return 1


def main() -> int:
    """Main entry point for notification job."""
    try:
        exit_code = asyncio.run(run_notification_job())
        return exit_code
    except KeyboardInterrupt:
        logger.info("Notification job interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Unexpected error in notification job: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
