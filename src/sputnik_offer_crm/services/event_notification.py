"""Event-based notification service for direct user notifications."""

from datetime import date

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from sputnik_offer_crm.config import get_settings
from sputnik_offer_crm.models import Stage, Student
from sputnik_offer_crm.utils.logging import get_logger

logger = get_logger(__name__)


class EventNotificationService:
    """Service for sending event-based notifications to users."""

    def __init__(self):
        self.settings = get_settings()

    async def _send_message(
        self,
        telegram_id: int,
        message: str,
        student_id: int | None = None,
    ) -> bool:
        """
        Send message to user via Telegram bot.

        Args:
            telegram_id: Telegram user ID
            message: message text
            student_id: optional student ID for logging

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            bot = Bot(
                token=self.settings.bot_token,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML),
            )

            try:
                await bot.send_message(
                    chat_id=telegram_id,
                    text=message,
                )
                logger.info(
                    "Event notification sent",
                    student_id=student_id,
                    telegram_id=telegram_id,
                )
                return True

            finally:
                await bot.session.close()

        except Exception as e:
            logger.error(
                "Failed to send event notification",
                student_id=student_id,
                telegram_id=telegram_id,
                error=str(e),
            )
            return False

    async def notify_registration_complete(
        self,
        student: Student,
        direction_name: str,
        first_stage_title: str,
    ) -> bool:
        """
        Send welcome notification after student registration.

        Args:
            student: registered student
            direction_name: direction name
            first_stage_title: first stage title

        Returns:
            True if sent successfully, False otherwise
        """
        message = (
            f"🎉 Добро пожаловать в Sputnik Offer CRM!\n\n"
            f"📚 Направление: {direction_name}\n"
            f"📍 Текущий этап: {first_stage_title}\n\n"
            f"Используйте меню для отправки отчётов и отслеживания прогресса."
        )

        return await self._send_message(
            telegram_id=student.telegram_id,
            message=message,
            student_id=student.id,
        )

    async def notify_stage_transition(
        self,
        student: Student,
        old_stage: Stage,
        new_stage: Stage,
    ) -> bool:
        """
        Send notification about stage transition.

        Args:
            student: student
            old_stage: previous stage
            new_stage: new stage

        Returns:
            True if sent successfully, False otherwise
        """
        message = (
            f"🎯 Переход на новый этап\n\n"
            f"✅ Завершён: {old_stage.title}\n"
            f"📍 Текущий этап: {new_stage.title}\n\n"
            f"Продолжайте работу над новым этапом!"
        )

        return await self._send_message(
            telegram_id=student.telegram_id,
            message=message,
            student_id=student.id,
        )

    async def notify_deadline_changed(
        self,
        student: Student,
        stage: Stage,
        new_deadline: date,
    ) -> bool:
        """
        Send notification about deadline change.

        Args:
            student: student
            stage: stage with changed deadline
            new_deadline: new deadline date

        Returns:
            True if sent successfully, False otherwise
        """
        message = (
            f"📅 Изменён дедлайн\n\n"
            f"📍 Этап: {stage.title}\n"
            f"📅 Новый дедлайн: {new_deadline.strftime('%d.%m.%Y')}\n\n"
            f"Планируйте работу с учётом нового срока."
        )

        return await self._send_message(
            telegram_id=student.telegram_id,
            message=message,
            student_id=student.id,
        )

    async def notify_bulk_deadlines_set(
        self,
        student: Student,
        stage_deadlines: list[tuple[str, date]],
    ) -> bool:
        """
        Send notification about bulk deadline setting.

        Args:
            student: student
            stage_deadlines: list of (stage_title, deadline_date) tuples

        Returns:
            True if sent successfully, False otherwise
        """
        deadlines_text = "\n".join(
            f"• {title}: {deadline.strftime('%d.%m.%Y')}"
            for title, deadline in stage_deadlines
        )

        message = (
            f"📅 Установлены дедлайны\n\n"
            f"{deadlines_text}\n\n"
            f"Планируйте работу с учётом этих сроков."
        )

        return await self._send_message(
            telegram_id=student.telegram_id,
            message=message,
            student_id=student.id,
        )

    async def notify_student_dropped(
        self,
        student: Student,
    ) -> bool:
        """
        Send notification about student dropout.

        Args:
            student: student

        Returns:
            True if sent successfully, False otherwise
        """
        message = (
            f"👋 Ваше участие в программе завершено\n\n"
            f"Спасибо за время, проведённое с нами.\n"
            f"Если у вас есть вопросы, обратитесь к ментору."
        )

        return await self._send_message(
            telegram_id=student.telegram_id,
            message=message,
            student_id=student.id,
        )

    async def notify_student_paused(
        self,
        student: Student,
    ) -> bool:
        """
        Send notification about student pause.

        Args:
            student: student

        Returns:
            True if sent successfully, False otherwise
        """
        message = (
            f"⏸️ Обучение приостановлено\n\n"
            f"Ваше участие в программе временно приостановлено.\n"
            f"Для возобновления обратитесь к ментору."
        )

        return await self._send_message(
            telegram_id=student.telegram_id,
            message=message,
            student_id=student.id,
        )

    async def notify_student_resumed(
        self,
        student: Student,
    ) -> bool:
        """
        Send notification about student resume.

        Args:
            student: student

        Returns:
            True if sent successfully, False otherwise
        """
        message = (
            f"▶️ Обучение возобновлено\n\n"
            f"Ваше участие в программе возобновлено.\n"
            f"Продолжайте работу над текущим этапом!"
        )

        return await self._send_message(
            telegram_id=student.telegram_id,
            message=message,
            student_id=student.id,
        )

    async def notify_offer_received(
        self,
        student: Student,
        company: str,
        position: str,
    ) -> bool:
        """
        Send notification about offer completion.

        Args:
            student: student
            company: company name
            position: position title

        Returns:
            True if sent successfully, False otherwise
        """
        message = (
            f"🎉 Поздравляем с получением оффера!\n\n"
            f"🏢 Компания: {company}\n"
            f"💼 Позиция: {position}\n\n"
            f"Отличная работа! Желаем успехов на новом месте!"
        )

        return await self._send_message(
            telegram_id=student.telegram_id,
            message=message,
            student_id=student.id,
        )
