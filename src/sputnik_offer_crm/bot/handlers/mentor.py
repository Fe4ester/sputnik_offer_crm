"""Mentor handlers."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup

from sputnik_offer_crm.bot.keyboards import (
    get_direction_selection_keyboard,
    get_mentor_menu_keyboard,
    get_timezone_keyboard,
)
from sputnik_offer_crm.bot.keyboards.mentor import get_mentor_timezone_fallback_keyboard
from sputnik_offer_crm.bot.states import MentorInviteCodeStates, MentorStudentViewStates
from sputnik_offer_crm.db import get_session
from sputnik_offer_crm.services import (
    InviteCodeGenerationError,
    MentorNotFoundError,
    MentorService,
    MentorStudentService,
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


@router.message(F.text == "👤 Найти ученика")
async def start_student_search(message: Message, state: FSMContext) -> None:
    """Start student search flow."""
    async with get_session() as session:
        service = MentorService(session)

        try:
            await service.check_mentor_access(message.from_user.id)
        except MentorNotFoundError:
            await message.answer("❌ Доступ запрещён. Вы не являетесь ментором.")
            return

        await message.answer(
            "🔍 Поиск ученика\n\n"
            "Введите для поиска:\n"
            "• Telegram username (с @ или без)\n"
            "• Имя или фамилию\n"
            "• Telegram ID"
        )
        await state.set_state(MentorStudentViewStates.waiting_for_search_query)


@router.message(MentorStudentViewStates.waiting_for_search_query)
async def process_student_search(message: Message, state: FSMContext) -> None:
    """Process student search query."""
    if not message.text:
        await message.answer("Пожалуйста, отправьте текстовое сообщение.")
        return

    query = message.text.strip()

    async with get_session() as session:
        service = MentorStudentService(session)
        results = await service.search_students(query)

        if not results:
            await message.answer(
                f"❌ Ученики не найдены по запросу: {query}\n\n"
                "Попробуйте другой запрос или проверьте правильность ввода.",
                reply_markup=get_mentor_menu_keyboard(),
            )
            await state.clear()
            return

        if len(results) == 1:
            # Single result - show card immediately
            await state.clear()
            await show_student_card(message, results[0].student.id)
            return

        # Multiple results - show selection
        buttons = []
        for result in results:
            student = result.student
            display_name = f"{student.first_name}"
            if student.last_name:
                display_name += f" {student.last_name}"
            if student.username:
                display_name += f" (@{student.username})"
            if result.direction_name:
                display_name += f" — {result.direction_name}"

            buttons.append([
                InlineKeyboardButton(
                    text=display_name,
                    callback_data=f"student:{student.id}"
                )
            ])

        buttons.append([
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_search")
        ])

        await message.answer(
            f"🔍 Найдено учеников: {len(results)}\n\n"
            "Выберите ученика:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        )
        await state.clear()


@router.callback_query(F.data.startswith("student:"))
async def handle_student_selection(callback: CallbackQuery) -> None:
    """Handle student selection from search results."""
    await callback.answer()

    student_id = int(callback.data.split(":", 1)[1])
    await callback.message.delete()
    await show_student_card(callback.message, student_id)


@router.callback_query(F.data == "cancel_search")
async def handle_search_cancel(callback: CallbackQuery) -> None:
    """Handle search cancellation."""
    await callback.answer()
    await callback.message.edit_text("❌ Поиск отменён.")


async def show_student_card(message: Message, student_id: int) -> None:
    """Show student card to mentor."""
    async with get_session() as session:
        service = MentorStudentService(session)
        card = await service.get_student_card(student_id)

        if not card:
            await message.answer(
                "❌ Информация об ученике не найдена.",
                reply_markup=get_mentor_menu_keyboard(),
            )
            return

        # Build card text
        lines = ["👤 Карточка ученика\n"]

        # Basic info
        lines.append(f"📛 Имя: {card.student.first_name}")
        if card.student.last_name:
            lines.append(f"   Фамилия: {card.student.last_name}")
        if card.student.username:
            lines.append(f"💬 Username: @{card.student.username}")
        lines.append(f"🆔 Telegram ID: {card.student.telegram_id}")
        lines.append("")

        # Progress info
        lines.append(f"📚 Направление: {card.direction.name}")
        lines.append(f"📍 Текущий этап: {card.current_stage.title}")
        started_date = card.progress.started_at.strftime("%d.%m.%Y")
        lines.append(f"📅 Дата старта: {started_date}")
        lines.append(f"🌍 Часовой пояс: {card.student.timezone}")
        status_emoji = "✅" if card.student.is_active else "⏸"
        status_text = "Активен" if card.student.is_active else "Неактивен"
        lines.append(f"{status_emoji} Статус: {status_text}")
        lines.append("")

        # Deadlines
        if card.deadlines:
            lines.append("📅 Ближайшие дедлайны:")
            for deadline in card.deadlines[:5]:  # Show max 5
                status_emoji = "⚠️" if deadline.is_overdue else "📌"
                date_str = deadline.deadline_date.strftime("%d.%m.%Y")
                lines.append(f"{status_emoji} {deadline.title}")
                lines.append(f"   Срок: {date_str}")
                if deadline.is_overdue:
                    lines.append("   (просрочен)")
            lines.append("")
        else:
            lines.append("📅 Дедлайны: не назначены\n")

        # Weekly reports
        if card.recent_reports:
            lines.append("📝 Последние отчёты:")
            for report in card.recent_reports:
                week_str = report.week_start_date.strftime("%d.%m.%Y")
                lines.append(f"\n📅 Неделя с {week_str}:")
                
                # Truncate long answers
                what_did = report.answer_what_did
                if len(what_did) > 150:
                    what_did = what_did[:150] + "..."
                lines.append(f"• Что делал: {what_did}")
                
                if report.answer_problems_solved:
                    solved = report.answer_problems_solved
                    if len(solved) > 100:
                        solved = solved[:100] + "..."
                    lines.append(f"• Решённые проблемы: {solved}")
                
                if report.answer_problems_unsolved:
                    unsolved = report.answer_problems_unsolved
                    if len(unsolved) > 100:
                        unsolved = unsolved[:100] + "..."
                    lines.append(f"• Нужна помощь: {unsolved}")
        else:
            lines.append("📝 Отчёты: пока не отправлялись")

        await message.answer(
            "\n".join(lines),
            reply_markup=get_mentor_menu_keyboard(),
        )

        logger.info(
            "Mentor viewed student card",
            mentor_id=message.from_user.id,
            student_id=student_id,
        )
