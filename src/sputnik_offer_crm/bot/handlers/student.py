"""Student handlers."""

from aiogram import F, Router
from aiogram.types import Message

from sputnik_offer_crm.bot.keyboards import get_student_menu_keyboard
from sputnik_offer_crm.db import get_session
from sputnik_offer_crm.services import StudentService
from sputnik_offer_crm.utils.logging import get_logger

router = Router(name="student")
logger = get_logger(__name__)


async def show_student_menu(message: Message) -> None:
    """Show main menu for student."""
    await message.answer(
        "📚 Главное меню\n\n"
        "Выберите действие:",
        reply_markup=get_student_menu_keyboard(),
    )


@router.message(F.text == "📊 Мой прогресс")
async def show_my_progress(message: Message) -> None:
    """Show student progress information."""
    async with get_session() as session:
        service = StudentService(session)
        progress_info = await service.get_student_progress(message.from_user.id)

        if not progress_info:
            await message.answer(
                "❌ Не удалось загрузить информацию о прогрессе.\n\n"
                "Обратитесь к ментору."
            )
            return

        # Format started_at date
        started_date = progress_info.progress.started_at.strftime("%d.%m.%Y")

        await message.answer(
            f"📊 Ваш прогресс\n\n"
            f"📚 Направление: {progress_info.direction.name}\n"
            f"📍 Текущий этап: {progress_info.current_stage.name}\n"
            f"📅 Дата старта: {started_date}\n"
            f"🌍 Часовой пояс: {progress_info.student.timezone}\n\n"
            f"Продолжайте в том же духе! 💪"
        )


@router.message(F.text == "📅 Мои дедлайны")
async def show_my_deadlines(message: Message) -> None:
    """Show student deadlines."""
    async with get_session() as session:
        service = StudentService(session)
        deadlines = await service.get_student_deadlines(message.from_user.id)

        if not deadlines:
            await message.answer(
                "📅 Дедлайны\n\n"
                "У вас пока нет назначенных дедлайнов.\n"
                "Ментор установит их позже."
            )
            return

        # Future implementation: format and display deadlines
        # For now, this branch won't be reached as get_student_deadlines returns []
