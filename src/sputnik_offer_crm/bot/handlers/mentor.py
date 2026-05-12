"""Mentor handlers."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from sputnik_offer_crm.bot.keyboards import (
    get_direction_selection_keyboard,
    get_mentor_menu_keyboard,
    get_timezone_keyboard,
)
from sputnik_offer_crm.bot.keyboards.mentor import get_mentor_timezone_fallback_keyboard
from sputnik_offer_crm.bot.states import MentorInviteCodeStates
from sputnik_offer_crm.db import get_session
from sputnik_offer_crm.services import (
    InviteCodeGenerationError,
    MentorNotFoundError,
    MentorService,
)
from sputnik_offer_crm.utils.logging import get_logger

router = Router(name="mentor")
logger = get_logger(__name__)


async def show_mentor_menu(message: Message) -> None:
    """Show main menu for mentor."""
    await message.answer(
        "👨‍🏫 Меню ментора\n\n"
        "Выберите действие:",
        reply_markup=get_mentor_menu_keyboard(),
    )


@router.message(F.text == "➕ Новый код доступа")
async def start_invite_code_creation(message: Message, state: FSMContext) -> None:
    """Start invite code creation flow."""
    async with get_session() as session:
        service = MentorService(session)

        try:
            mentor = await service.check_mentor_access(message.from_user.id)
        except MentorNotFoundError:
            await message.answer("❌ Доступ запрещён. Вы не являетесь ментором.")
            return

        # Get active directions
        directions = await service.get_active_directions()

        if not directions:
            await message.answer(
                "❌ Нет доступных направлений.\n\n"
                "Обратитесь к администратору для настройки направлений."
            )
            return

        await message.answer(
            "📚 Выберите направление для нового кода доступа:",
            reply_markup=get_direction_selection_keyboard(directions),
        )
        await state.set_state(MentorInviteCodeStates.selecting_direction)


@router.callback_query(MentorInviteCodeStates.selecting_direction, F.data.startswith("dir:"))
async def handle_direction_selection(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle direction selection."""
    await callback.answer()

    direction_id = int(callback.data.split(":", 1)[1])

    # Store direction_id in FSM data
    await state.update_data(direction_id=direction_id)

    await callback.message.edit_text(
        "🌍 Выберите рекомендуемый часовой пояс для ученика:\n\n"
        "(Ученик сможет изменить его при регистрации)",
        reply_markup=get_timezone_keyboard(),
    )
    await state.set_state(MentorInviteCodeStates.selecting_timezone)


@router.callback_query(MentorInviteCodeStates.selecting_direction, F.data == "cancel")
async def handle_direction_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle direction selection cancellation."""
    await callback.answer()
    await callback.message.edit_text("❌ Создание кода отменено.")
    await state.clear()


@router.callback_query(MentorInviteCodeStates.selecting_timezone, F.data.startswith("tz:"))
async def handle_timezone_selection(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle timezone selection for invite code."""
    await callback.answer()

    timezone_data = callback.data.split(":", 1)[1]

    # Handle "other" - show mentor-specific fallback keyboard
    if timezone_data == "other":
        await callback.message.edit_text(
            "🌍 Выберите часовой пояс:",
            reply_markup=get_mentor_timezone_fallback_keyboard(),
        )
        return

    # Handle "back"
    if timezone_data == "back":
        await callback.message.edit_text(
            "🌍 Выберите рекомендуемый часовой пояс для ученика:\n\n"
            "(Ученик сможет изменить его при регистрации)",
            reply_markup=get_timezone_keyboard(),
        )
        return

    # Validate timezone value - must not be a technical callback
    if timezone_data in ("input_time", "confirm"):
        logger.warning(
            "Invalid timezone callback in mentor flow",
            callback_data=timezone_data,
            mentor_id=callback.from_user.id,
        )
        await callback.message.edit_text(
            "❌ Ошибка выбора часового пояса. Попробуйте снова.",
            reply_markup=get_timezone_keyboard(),
        )
        return

    # Create invite code with validated timezone
    await create_invite_code(callback, state, timezone_data)


async def create_invite_code(
    callback: CallbackQuery, state: FSMContext, timezone_str: str
) -> None:
    """Create invite code and show it to mentor."""
    data = await state.get_data()
    direction_id = data.get("direction_id")

    if not direction_id:
        await callback.message.edit_text(
            "❌ Ошибка: направление не выбрано. Начните создание кода заново."
        )
        await state.clear()
        return

    async with get_session() as session:
        service = MentorService(session)

        try:
            mentor = await service.check_mentor_access(callback.from_user.id)
        except MentorNotFoundError:
            await callback.message.edit_text("❌ Доступ запрещён.")
            await state.clear()
            return

        # Get direction name for display
        from sputnik_offer_crm.models import Direction
        from sqlalchemy import select

        result = await session.execute(
            select(Direction).where(Direction.id == direction_id)
        )
        direction = result.scalar_one_or_none()

        if not direction or not direction.is_active:
            await callback.message.edit_text(
                "❌ Направление недоступно. Начните создание кода заново."
            )
            await state.clear()
            return

        try:
            invite_code = await service.create_invite_code(
                mentor_id=mentor.id,
                direction_id=direction_id,
                suggested_timezone=timezone_str,
            )

            await callback.message.edit_text(
                f"✅ Код доступа создан!\n\n"
                f"🔑 Код: <code>{invite_code.code}</code>\n"
                f"📚 Направление: {direction.name}\n"
                f"🌍 Рекомендуемый часовой пояс: {timezone_str}\n\n"
                f"ℹ️ Код одноразовый и действует до первого использования.\n"
                f"Отправьте его ученику для регистрации."
            )

            logger.info(
                "Invite code created",
                mentor_id=mentor.id,
                code=invite_code.code,
                direction_id=direction_id,
            )

        except InviteCodeGenerationError as e:
            logger.error("Failed to generate invite code", error=str(e))
            await callback.message.edit_text(
                "❌ Не удалось создать код. Попробуйте позже или обратитесь к администратору."
            )
        except Exception as e:
            logger.error("Invite code creation failed", error=str(e), exc_info=True)
            await callback.message.edit_text(
                "❌ Произошла ошибка при создании кода. Попробуйте позже."
            )
        finally:
            await state.clear()
