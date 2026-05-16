"""Mentor handlers."""

from datetime import date

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup

from sputnik_offer_crm.bot.keyboards import (
    get_direction_selection_keyboard,
    get_mentor_menu_keyboard,
    get_timezone_keyboard,
)
from sputnik_offer_crm.bot.keyboards.mentor import get_mentor_timezone_fallback_keyboard
from sputnik_offer_crm.bot.states import MentorInviteCodeStates, MentorStudentViewStates, MentorTaskCreationStates
from sputnik_offer_crm.db import get_session
from sputnik_offer_crm.services import (
    AlreadyOnFinalStageError,
    AlreadyOnThisStageError,
    DeadlineManagementError,
    DeadlineStudentHasNoProgressError,
    DeadlineStudentNotFoundError,
    EventNotificationService,
    InviteCodeGenerationError,
    InvalidDeadlineDateError,
    ManualStageSelectionError,
    MentorDeadlineService,
    MentorNotFoundError,
    MentorOfferCompletionService,
    MentorPauseResumeService,
    MentorProgressService,
    MentorService,
    MentorStudentService,
    MentorStudentStatusService,
    MoveToNextStageError,
    NoStagesFoundError,
    OfferCompletionError,
    OfferCompletionStudentNotFoundError,
    PauseResumeError,
    PauseResumeStudentInactiveError,
    PauseResumeStudentNotFoundError,
    StageNotFoundError,
    StageNotInDirectionError,
    StatusStudentNotFoundError,
    StudentAlreadyCompletedError,
    StudentAlreadyInactiveError,
    StudentAlreadyPausedError,
    StudentHasNoProgressError,
    StudentInactiveError,
    StudentNotFoundError as ProgressStudentNotFoundError,
    StudentNotPausedError,
    StudentStatusManagementError,
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
    await callback.message.answer(
        "👨‍🏫 Меню ментора\n\nВыберите действие:",
        reply_markup=get_mentor_menu_keyboard(),
    )


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

        # Status with pause indication
        if not card.student.is_active:
            status_emoji = "⏸"
            status_text = "Неактивен (отчислен)"
        elif card.student.is_paused:
            status_emoji = "⏸"
            status_text = "На паузе"
        else:
            status_emoji = "✅"
            status_text = "Активен"
        lines.append(f"{status_emoji} Статус: {status_text}")

        # Offer info if completed
        if card.student.offer_received_at:
            lines.append("")
            lines.append("🎉 Завершён с оффером:")
            lines.append(f"🏢 Компания: {card.student.offer_company}")
            lines.append(f"💼 Позиция: {card.student.offer_position}")
            offer_date = card.student.offer_received_at.strftime("%d.%m.%Y")
            lines.append(f"📅 Дата получения: {offer_date}")

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

        # Add action buttons
        buttons = [
            [
                InlineKeyboardButton(
                    text="➡️ Перевести на следующий этап",
                    callback_data=f"move_next:{student_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎯 Выбрать этап вручную",
                    callback_data=f"select_stage:{student_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📅 Изменить дедлайн текущего этапа",
                    callback_data=f"change_deadline:{student_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 Установить дедлайны для всех этапов",
                    callback_data=f"bulk_deadlines:{student_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ Завершить / получил оффер",
                    callback_data=f"offer_completion:{student_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📌 Добавить задачу",
                    callback_data=f"add_task:{student_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 Задачи ученика",
                    callback_data=f"view_student_tasks:{student_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📝 Отчёты ученика",
                    callback_data=f"view_student_reports:{student_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📊 Прогресс детальный",
                    callback_data=f"detailed_progress:{student_id}"
                )
            ],
        ]

        # Add pause/resume button based on current state
        if card.student.is_active:
            if card.student.is_paused:
                buttons.append([
                    InlineKeyboardButton(
                        text="▶️ Возобновить",
                        callback_data=f"resume:{student_id}"
                    )
                ])
            else:
                buttons.append([
                    InlineKeyboardButton(
                        text="⏸ Поставить на паузу",
                        callback_data=f"pause:{student_id}"
                    )
                ])

        # Add dropout button
        buttons.append([
            InlineKeyboardButton(
                text="❌ Отчислить",
                callback_data=f"dropout:{student_id}"
            )
        ])

        await message.answer(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        )

        logger.info(
            "Mentor viewed student card",
            mentor_id=message.from_user.id,
            student_id=student_id,
        )


@router.callback_query(F.data.startswith("move_next:"))
async def handle_move_to_next_stage_request(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle request to move student to next stage."""
    await callback.answer()

    student_id = int(callback.data.split(":", 1)[1])

    async with get_session() as session:
        # Check mentor access
        mentor_service = MentorService(session)
        try:
            await mentor_service.check_mentor_access(callback.from_user.id)
        except MentorNotFoundError:
            await callback.message.edit_text("❌ Доступ запрещён. Вы не являетесь ментором.")
            return

        # Get next stage info
        progress_service = MentorProgressService(session)
        try:
            info = await progress_service.get_next_stage_info(student_id)
        except ProgressStudentNotFoundError:
            await callback.message.edit_text(
                "❌ Ученик не найден.",
                reply_markup=get_mentor_menu_keyboard(),
            )
            return
        except StudentHasNoProgressError:
            await callback.message.edit_text(
                "❌ У ученика нет записи о прогрессе.",
                reply_markup=get_mentor_menu_keyboard(),
            )
            return
        except AlreadyOnFinalStageError:
            await callback.message.edit_text(
                "ℹ️ Ученик уже находится на финальном этапе.\n\n"
                f"Текущий этап: {info.current_stage.title if 'info' in locals() else 'неизвестен'}",
                reply_markup=get_mentor_menu_keyboard(),
            )
            return
        except MoveToNextStageError as e:
            logger.error("Failed to get next stage info", error=str(e))
            await callback.message.edit_text(
                "❌ Не удалось получить информацию о следующем этапе.",
                reply_markup=get_mentor_menu_keyboard(),
            )
            return

        # Show confirmation
        student_name = info.student.first_name
        if info.student.last_name:
            student_name += f" {info.student.last_name}"

        confirmation_text = (
            f"➡️ Перевод на следующий этап\n\n"
            f"👤 Ученик: {student_name}\n\n"
            f"📍 Текущий этап:\n{info.current_stage.title}\n\n"
            f"➡️ Следующий этап:\n{info.next_stage.title}\n\n"
            f"Подтвердите перевод:"
        )

        buttons = [
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_move:{student_id}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel_move:{student_id}"),
            ]
        ]

        await callback.message.edit_text(
            confirmation_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        )

        # Store student_id in state for confirmation
        await state.update_data(student_id=student_id)
        await state.set_state(MentorStudentViewStates.confirming_next_stage)


@router.callback_query(MentorStudentViewStates.confirming_next_stage, F.data.startswith("confirm_move:"))
async def handle_confirm_move_to_next_stage(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle confirmation of move to next stage."""
    await callback.answer()

    student_id = int(callback.data.split(":", 1)[1])

    async with get_session() as session:
        # Check mentor access
        mentor_service = MentorService(session)
        try:
            await mentor_service.check_mentor_access(callback.from_user.id)
        except MentorNotFoundError:
            await callback.message.edit_text("❌ Доступ запрещён.")
            await state.clear()
            return

        # Perform the move
        progress_service = MentorProgressService(session)
        try:
            # Get stage info before move
            info = await progress_service.get_next_stage_info(student_id)
            old_stage = info.current_stage
            student = info.student

            next_stage = await progress_service.move_to_next_stage(student_id)

            await callback.message.edit_text(
                f"✅ Ученик успешно переведён на следующий этап!\n\n"
                f"➡️ Новый этап: {next_stage.title}"
            )

            logger.info(
                "Student moved to next stage",
                mentor_id=callback.from_user.id,
                student_id=student_id,
                new_stage_id=next_stage.id,
            )

            # Send notification to student
            notification_service = EventNotificationService()
            await notification_service.notify_stage_transition(
                student=student,
                old_stage=old_stage,
                new_stage=next_stage,
            )

            # Show updated card
            await show_student_card(callback.message, student_id)

        except ProgressStudentNotFoundError:
            await callback.message.edit_text(
                "❌ Ученик не найден.",
                reply_markup=get_mentor_menu_keyboard(),
            )
        except StudentHasNoProgressError:
            await callback.message.edit_text(
                "❌ У ученика нет записи о прогрессе.",
                reply_markup=get_mentor_menu_keyboard(),
            )
        except AlreadyOnFinalStageError:
            await callback.message.edit_text(
                "ℹ️ Ученик уже находится на финальном этапе.",
                reply_markup=get_mentor_menu_keyboard(),
            )
        except MoveToNextStageError as e:
            logger.error("Failed to move student to next stage", error=str(e), exc_info=True)
            await callback.message.edit_text(
                "❌ Не удалось перевести ученика на следующий этап.",
                reply_markup=get_mentor_menu_keyboard(),
            )
        finally:
            await state.clear()


@router.callback_query(MentorStudentViewStates.confirming_next_stage, F.data.startswith("cancel_move:"))
async def handle_cancel_move_to_next_stage(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle cancellation of move to next stage."""
    await callback.answer()

    student_id = int(callback.data.split(":", 1)[1])

    await callback.message.edit_text("❌ Перевод отменён.")
    await state.clear()

    # Show card again
    await show_student_card(callback.message, student_id)


@router.callback_query(F.data.startswith("select_stage:"))
async def handle_select_stage_request(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle request to select stage manually."""
    await callback.answer()

    student_id = int(callback.data.split(":", 1)[1])

    async with get_session() as session:
        # Check mentor access
        mentor_service = MentorService(session)
        try:
            await mentor_service.check_mentor_access(callback.from_user.id)
        except MentorNotFoundError:
            await callback.message.edit_text("❌ Доступ запрещён. Вы не являетесь ментором.")
            return

        # Get available stages
        progress_service = MentorProgressService(session)
        try:
            stages = await progress_service.get_available_stages(student_id)
        except ProgressStudentNotFoundError:
            await callback.message.edit_text(
                "❌ Ученик не найден.",
                reply_markup=get_mentor_menu_keyboard(),
            )
            return
        except StudentHasNoProgressError:
            await callback.message.edit_text(
                "❌ У ученика нет записи о прогрессе.",
                reply_markup=get_mentor_menu_keyboard(),
            )
            return
        except Exception as e:
            logger.error("Failed to get available stages", error=str(e))
            await callback.message.edit_text(
                "❌ Не удалось получить список этапов.",
                reply_markup=get_mentor_menu_keyboard(),
            )
            return

        if not stages:
            await callback.message.edit_text(
                "❌ Нет доступных этапов в направлении ученика.",
                reply_markup=get_mentor_menu_keyboard(),
            )
            return

        # Show stage selection
        buttons = []
        for stage in stages:
            buttons.append([
                InlineKeyboardButton(
                    text=f"{stage.stage_number}. {stage.title}",
                    callback_data=f"stage:{student_id}:{stage.id}"
                )
            ])

        buttons.append([
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel_select:{student_id}")
        ])

        await callback.message.edit_text(
            "🎯 Выбор этапа вручную\n\n"
            "Выберите этап для ученика:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        )

        await state.update_data(student_id=student_id)
        await state.set_state(MentorStudentViewStates.selecting_manual_stage)


@router.callback_query(MentorStudentViewStates.selecting_manual_stage, F.data.startswith("stage:"))
async def handle_stage_selection(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle stage selection."""
    await callback.answer()

    parts = callback.data.split(":", 2)
    student_id = int(parts[1])
    stage_id = int(parts[2])

    async with get_session() as session:
        # Check mentor access
        mentor_service = MentorService(session)
        try:
            await mentor_service.check_mentor_access(callback.from_user.id)
        except MentorNotFoundError:
            await callback.message.edit_text("❌ Доступ запрещён.")
            await state.clear()
            return

        # Get stage info and student info
        progress_service = MentorProgressService(session)
        from sputnik_offer_crm.models import Stage, Student, StudentProgress
        from sqlalchemy import select

        try:
            # Get student
            result = await session.execute(
                select(Student).where(Student.id == student_id)
            )
            student = result.scalar_one_or_none()

            if not student:
                await callback.message.edit_text(
                    "❌ Ученик не найден.",
                    reply_markup=get_mentor_menu_keyboard(),
                )
                await state.clear()
                return

            # Get student progress
            result = await session.execute(
                select(StudentProgress).where(StudentProgress.student_id == student_id)
            )
            progress = result.scalar_one_or_none()

            if not progress:
                await callback.message.edit_text(
                    "❌ У ученика нет записи о прогрессе.",
                    reply_markup=get_mentor_menu_keyboard(),
                )
                await state.clear()
                return

            # Get current stage
            result = await session.execute(
                select(Stage).where(Stage.id == progress.current_stage_id)
            )
            current_stage = result.scalar_one()

            # Get target stage
            result = await session.execute(
                select(Stage).where(Stage.id == stage_id)
            )
            target_stage = result.scalar_one_or_none()

            if not target_stage:
                await callback.message.edit_text(
                    "❌ Выбранный этап не найден.",
                    reply_markup=get_mentor_menu_keyboard(),
                )
                await state.clear()
                return

            # Check if already on this stage
            if progress.current_stage_id == stage_id:
                await callback.message.edit_text(
                    f"ℹ️ Ученик уже находится на этом этапе.\n\n"
                    f"Текущий этап: {current_stage.title}",
                    reply_markup=get_mentor_menu_keyboard(),
                )
                await state.clear()
                return

            # Show confirmation
            student_name = student.first_name
            if student.last_name:
                student_name += f" {student.last_name}"

            confirmation_text = (
                f"🎯 Ручной выбор этапа\n\n"
                f"👤 Ученик: {student_name}\n\n"
                f"📍 Текущий этап:\n{current_stage.title}\n\n"
                f"➡️ Новый этап:\n{target_stage.title}\n\n"
                f"Подтвердите перевод:"
            )

            buttons = [
                [
                    InlineKeyboardButton(
                        text="✅ Подтвердить",
                        callback_data=f"confirm_manual:{student_id}:{stage_id}"
                    ),
                    InlineKeyboardButton(
                        text="❌ Отмена",
                        callback_data=f"cancel_manual:{student_id}"
                    ),
                ]
            ]

            await callback.message.edit_text(
                confirmation_text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            )

            await state.update_data(student_id=student_id, stage_id=stage_id)
            await state.set_state(MentorStudentViewStates.confirming_manual_stage)

        except Exception as e:
            logger.error("Failed to prepare stage selection confirmation", error=str(e), exc_info=True)
            await callback.message.edit_text(
                "❌ Произошла ошибка при подготовке подтверждения.",
                reply_markup=get_mentor_menu_keyboard(),
            )
            await state.clear()


@router.callback_query(MentorStudentViewStates.selecting_manual_stage, F.data.startswith("cancel_select:"))
async def handle_cancel_stage_selection(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle cancellation of stage selection."""
    await callback.answer()

    student_id = int(callback.data.split(":", 1)[1])

    await callback.message.edit_text("❌ Выбор этапа отменён.")
    await state.clear()

    # Show card again
    await show_student_card(callback.message, student_id)


@router.callback_query(MentorStudentViewStates.confirming_manual_stage, F.data.startswith("confirm_manual:"))
async def handle_confirm_manual_stage(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle confirmation of manual stage selection."""
    await callback.answer()

    parts = callback.data.split(":", 2)
    student_id = int(parts[1])
    stage_id = int(parts[2])

    async with get_session() as session:
        # Check mentor access
        mentor_service = MentorService(session)
        try:
            await mentor_service.check_mentor_access(callback.from_user.id)
        except MentorNotFoundError:
            await callback.message.edit_text("❌ Доступ запрещён.")
            await state.clear()
            return

        # Perform the move
        progress_service = MentorProgressService(session)
        try:
            # Get current stage info before move
            from sputnik_offer_crm.models import Student, StudentProgress, Stage
            from sqlalchemy import select

            result = await session.execute(
                select(Student, StudentProgress, Stage)
                .join(StudentProgress, StudentProgress.student_id == Student.id)
                .join(Stage, Stage.id == StudentProgress.current_stage_id)
                .where(Student.id == student_id)
            )
            row = result.one_or_none()
            if row:
                student, _, old_stage = row
            else:
                student = None
                old_stage = None

            target_stage = await progress_service.move_to_stage(student_id, stage_id)

            await callback.message.edit_text(
                f"✅ Ученик успешно переведён на выбранный этап!\n\n"
                f"➡️ Новый этап: {target_stage.title}"
            )

            logger.info(
                "Student moved to stage manually",
                mentor_id=callback.from_user.id,
                student_id=student_id,
                new_stage_id=target_stage.id,
            )

            # Send notification to student
            if student and old_stage:
                notification_service = EventNotificationService()
                await notification_service.notify_stage_transition(
                    student=student,
                    old_stage=old_stage,
                    new_stage=target_stage,
                )

            # Show updated card
            await show_student_card(callback.message, student_id)

        except ProgressStudentNotFoundError:
            await callback.message.edit_text(
                "❌ Ученик не найден.",
                reply_markup=get_mentor_menu_keyboard(),
            )
        except StudentHasNoProgressError:
            await callback.message.edit_text(
                "❌ У ученика нет записи о прогрессе.",
                reply_markup=get_mentor_menu_keyboard(),
            )
        except StageNotFoundError:
            await callback.message.edit_text(
                "❌ Выбранный этап не найден.",
                reply_markup=get_mentor_menu_keyboard(),
            )
        except StageNotInDirectionError:
            await callback.message.edit_text(
                "❌ Выбранный этап не принадлежит направлению ученика.",
                reply_markup=get_mentor_menu_keyboard(),
            )
        except AlreadyOnThisStageError:
            await callback.message.edit_text(
                "ℹ️ Ученик уже находится на этом этапе.",
                reply_markup=get_mentor_menu_keyboard(),
            )
        except ManualStageSelectionError as e:
            logger.error("Failed to move student to stage manually", error=str(e), exc_info=True)
            await callback.message.edit_text(
                "❌ Не удалось перевести ученика на выбранный этап.",
                reply_markup=get_mentor_menu_keyboard(),
            )
        finally:
            await state.clear()


@router.callback_query(MentorStudentViewStates.confirming_manual_stage, F.data.startswith("cancel_manual:"))
async def handle_cancel_manual_stage(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle cancellation of manual stage selection."""
    await callback.answer()

    student_id = int(callback.data.split(":", 1)[1])

    await callback.message.edit_text("❌ Перевод отменён.")
    await state.clear()

    # Show card again
    await show_student_card(callback.message, student_id)


@router.callback_query(F.data.startswith("change_deadline:"))
async def handle_change_deadline_request(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle request to change current stage deadline."""
    await callback.answer()

    student_id = int(callback.data.split(":", 1)[1])

    async with get_session() as session:
        # Check mentor access
        mentor_service = MentorService(session)
        try:
            await mentor_service.check_mentor_access(callback.from_user.id)
        except MentorNotFoundError:
            await callback.message.edit_text("❌ Доступ запрещён. Вы не являетесь ментором.")
            return

        # Get current stage and deadline
        deadline_service = MentorDeadlineService(session)
        try:
            current_stage, current_deadline = await deadline_service.get_current_stage_deadline(
                student_id
            )
        except DeadlineStudentNotFoundError:
            await callback.message.edit_text(
                "❌ Ученик не найден.",
                reply_markup=get_mentor_menu_keyboard(),
            )
            return
        except DeadlineStudentHasNoProgressError:
            await callback.message.edit_text(
                "❌ У ученика нет записи о прогрессе.",
                reply_markup=get_mentor_menu_keyboard(),
            )
            return
        except Exception as e:
            logger.error("Failed to get current stage deadline", error=str(e))
            await callback.message.edit_text(
                "❌ Не удалось получить информацию о дедлайне.",
                reply_markup=get_mentor_menu_keyboard(),
            )
            return

        # Show deadline options
        from datetime import date, timedelta

        today = date.today()
        deadline_text = (
            f"📅 Изменение дедлайна текущего этапа\n\n"
            f"📍 Текущий этап: {current_stage.title}\n"
        )

        if current_deadline:
            deadline_str = current_deadline.strftime("%d.%m.%Y")
            deadline_text += f"⏰ Текущий дедлайн: {deadline_str}\n\n"
        else:
            deadline_text += "⏰ Дедлайн не установлен\n\n"

        deadline_text += "Выберите новый дедлайн:"

        buttons = [
            [
                InlineKeyboardButton(
                    text=f"📅 +3 дня ({(today + timedelta(days=3)).strftime('%d.%m')})",
                    callback_data=f"deadline_days:{student_id}:3"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"📅 +7 дней ({(today + timedelta(days=7)).strftime('%d.%m')})",
                    callback_data=f"deadline_days:{student_id}:7"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"📅 +14 дней ({(today + timedelta(days=14)).strftime('%d.%m')})",
                    callback_data=f"deadline_days:{student_id}:14"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📝 Своя дата",
                    callback_data=f"deadline_custom:{student_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=f"cancel_deadline:{student_id}"
                )
            ],
        ]

        await callback.message.edit_text(
            deadline_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        )

        await state.update_data(student_id=student_id, current_stage_id=current_stage.id)
        await state.set_state(MentorStudentViewStates.selecting_deadline_option)


@router.callback_query(MentorStudentViewStates.selecting_deadline_option, F.data.startswith("deadline_days:"))
async def handle_deadline_days_selection(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle deadline selection with predefined days offset."""
    await callback.answer()

    parts = callback.data.split(":", 2)
    student_id = int(parts[1])
    days = int(parts[2])

    from datetime import date, timedelta

    new_deadline = date.today() + timedelta(days=days)

    # Show confirmation
    await show_deadline_confirmation(callback, state, student_id, new_deadline)


@router.callback_query(MentorStudentViewStates.selecting_deadline_option, F.data.startswith("deadline_custom:"))
async def handle_deadline_custom_request(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle request for custom deadline date."""
    await callback.answer()

    student_id = int(callback.data.split(":", 1)[1])

    await callback.message.edit_text(
        "📝 Введите дату дедлайна\n\n"
        "Формат: ДД.ММ.ГГГГ\n"
        "Например: 25.12.2026"
    )

    await state.update_data(student_id=student_id)
    await state.set_state(MentorStudentViewStates.waiting_for_custom_deadline)


@router.message(MentorStudentViewStates.waiting_for_custom_deadline)
async def handle_custom_deadline_input(message: Message, state: FSMContext) -> None:
    """Handle custom deadline date input."""
    if not message.text:
        await message.answer("Пожалуйста, отправьте текстовое сообщение с датой.")
        return

    date_str = message.text.strip()

    # Parse date
    from datetime import datetime

    try:
        new_deadline = datetime.strptime(date_str, "%d.%m.%Y").date()
    except ValueError:
        await message.answer(
            "❌ Неверный формат даты.\n\n"
            "Используйте формат: ДД.ММ.ГГГГ\n"
            "Например: 25.12.2026"
        )
        return

    # Validate date is not in the past
    from datetime import date

    if new_deadline < date.today():
        await message.answer(
            "❌ Дата не может быть в прошлом.\n\n"
            "Введите дату в будущем."
        )
        return

    data = await state.get_data()
    student_id = data.get("student_id")

    if not student_id:
        await message.answer(
            "❌ Ошибка: данные сессии потеряны. Начните заново.",
            reply_markup=get_mentor_menu_keyboard(),
        )
        await state.clear()
        return

    # Show confirmation
    await show_deadline_confirmation_message(message, state, student_id, new_deadline)


async def show_deadline_confirmation(
    callback: CallbackQuery, state: FSMContext, student_id: int, new_deadline: date
) -> None:
    """Show deadline change confirmation (for callback)."""
    async with get_session() as session:
        deadline_service = MentorDeadlineService(session)
        try:
            current_stage, current_deadline = await deadline_service.get_current_stage_deadline(
                student_id
            )

            deadline_str = new_deadline.strftime("%d.%m.%Y")
            confirmation_text = (
                f"📅 Подтверждение изменения дедлайна\n\n"
                f"📍 Этап: {current_stage.title}\n"
            )

            if current_deadline:
                old_deadline_str = current_deadline.strftime("%d.%m.%Y")
                confirmation_text += f"⏰ Текущий дедлайн: {old_deadline_str}\n"

            confirmation_text += f"➡️ Новый дедлайн: {deadline_str}\n\n"
            confirmation_text += "Подтвердите изменение:"

            buttons = [
                [
                    InlineKeyboardButton(
                        text="✅ Подтвердить",
                        callback_data=f"confirm_deadline:{student_id}:{new_deadline.isoformat()}"
                    ),
                    InlineKeyboardButton(
                        text="❌ Отмена",
                        callback_data=f"cancel_deadline:{student_id}"
                    ),
                ]
            ]

            await callback.message.edit_text(
                confirmation_text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            )

            await state.update_data(student_id=student_id, new_deadline=new_deadline.isoformat())
            await state.set_state(MentorStudentViewStates.confirming_deadline)

        except Exception as e:
            logger.error("Failed to show deadline confirmation", error=str(e), exc_info=True)
            await callback.message.edit_text(
                "❌ Произошла ошибка.",
                reply_markup=get_mentor_menu_keyboard(),
            )
            await state.clear()


async def show_deadline_confirmation_message(
    message: Message, state: FSMContext, student_id: int, new_deadline: date
) -> None:
    """Show deadline change confirmation (for message)."""
    async with get_session() as session:
        deadline_service = MentorDeadlineService(session)
        try:
            current_stage, current_deadline = await deadline_service.get_current_stage_deadline(
                student_id
            )

            deadline_str = new_deadline.strftime("%d.%m.%Y")
            confirmation_text = (
                f"📅 Подтверждение изменения дедлайна\n\n"
                f"📍 Этап: {current_stage.title}\n"
            )

            if current_deadline:
                old_deadline_str = current_deadline.strftime("%d.%m.%Y")
                confirmation_text += f"⏰ Текущий дедлайн: {old_deadline_str}\n"

            confirmation_text += f"➡️ Новый дедлайн: {deadline_str}\n\n"
            confirmation_text += "Подтвердите изменение:"

            buttons = [
                [
                    InlineKeyboardButton(
                        text="✅ Подтвердить",
                        callback_data=f"confirm_deadline:{student_id}:{new_deadline.isoformat()}"
                    ),
                    InlineKeyboardButton(
                        text="❌ Отмена",
                        callback_data=f"cancel_deadline:{student_id}"
                    ),
                ]
            ]

            await message.answer(
                confirmation_text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            )

            await state.update_data(student_id=student_id, new_deadline=new_deadline.isoformat())
            await state.set_state(MentorStudentViewStates.confirming_deadline)

        except Exception as e:
            logger.error("Failed to show deadline confirmation", error=str(e), exc_info=True)
            await message.answer(
                "❌ Произошла ошибка.",
                reply_markup=get_mentor_menu_keyboard(),
            )
            await state.clear()


@router.callback_query(MentorStudentViewStates.selecting_deadline_option, F.data.startswith("cancel_deadline:"))
@router.callback_query(MentorStudentViewStates.confirming_deadline, F.data.startswith("cancel_deadline:"))
async def handle_cancel_deadline(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle cancellation of deadline change."""
    await callback.answer()

    student_id = int(callback.data.split(":", 1)[1])

    await callback.message.edit_text("❌ Изменение дедлайна отменено.")
    await state.clear()

    # Show card again
    await show_student_card(callback.message, student_id)


@router.callback_query(MentorStudentViewStates.confirming_deadline, F.data.startswith("confirm_deadline:"))
async def handle_confirm_deadline(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle confirmation of deadline change."""
    await callback.answer()

    parts = callback.data.split(":", 2)
    student_id = int(parts[1])
    deadline_iso = parts[2]

    from datetime import date

    new_deadline = date.fromisoformat(deadline_iso)

    async with get_session() as session:
        # Check mentor access
        mentor_service = MentorService(session)
        try:
            await mentor_service.check_mentor_access(callback.from_user.id)
        except MentorNotFoundError:
            await callback.message.edit_text("❌ Доступ запрещён.")
            await state.clear()
            return

        # Set deadline
        deadline_service = MentorDeadlineService(session)
        try:
            # Get student info
            from sputnik_offer_crm.models import Student
            from sqlalchemy import select

            result = await session.execute(
                select(Student).where(Student.id == student_id)
            )
            student = result.scalar_one_or_none()

            current_stage = await deadline_service.set_current_stage_deadline(
                student_id, new_deadline
            )

            deadline_str = new_deadline.strftime("%d.%m.%Y")
            await callback.message.edit_text(
                f"✅ Дедлайн успешно изменён!\n\n"
                f"📍 Этап: {current_stage.title}\n"
                f"📅 Новый дедлайн: {deadline_str}"
            )

            logger.info(
                "Deadline changed for current stage",
                mentor_id=callback.from_user.id,
                student_id=student_id,
                stage_id=current_stage.id,
                new_deadline=deadline_iso,
            )

            # Send notification to student
            if student:
                notification_service = EventNotificationService()
                await notification_service.notify_deadline_changed(
                    student=student,
                    stage=current_stage,
                    new_deadline=new_deadline,
                )

            # Show updated card
            await show_student_card(callback.message, student_id)

        except DeadlineStudentNotFoundError:
            await callback.message.edit_text(
                "❌ Ученик не найден.",
                reply_markup=get_mentor_menu_keyboard(),
            )
        except DeadlineStudentHasNoProgressError:
            await callback.message.edit_text(
                "❌ У ученика нет записи о прогрессе.",
                reply_markup=get_mentor_menu_keyboard(),
            )
        except InvalidDeadlineDateError:
            await callback.message.edit_text(
                "❌ Некорректная дата дедлайна.",
                reply_markup=get_mentor_menu_keyboard(),
            )
        except DeadlineManagementError as e:
            logger.error("Failed to set deadline", error=str(e), exc_info=True)
            await callback.message.edit_text(
                "❌ Не удалось изменить дедлайн.",
                reply_markup=get_mentor_menu_keyboard(),
            )
        finally:
            await state.clear()


@router.callback_query(F.data.startswith("bulk_deadlines:"))
async def handle_bulk_deadlines_request(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle request to set bulk deadlines for all stages."""
    await callback.answer()

    student_id = int(callback.data.split(":", 1)[1])

    async with get_session() as session:
        # Check mentor access
        mentor_service = MentorService(session)
        try:
            await mentor_service.check_mentor_access(callback.from_user.id)
        except MentorNotFoundError:
            await callback.message.edit_text("❌ Доступ запрещён. Вы не являетесь ментором.")
            return

        # Calculate deadlines for all stages
        deadline_service = MentorDeadlineService(session)
        try:
            student, direction, previews = await deadline_service.calculate_all_stage_deadlines(
                student_id
            )
        except DeadlineStudentNotFoundError:
            await callback.message.edit_text(
                "❌ Ученик не найден.",
                reply_markup=get_mentor_menu_keyboard(),
            )
            return
        except DeadlineStudentHasNoProgressError:
            await callback.message.edit_text(
                "❌ У ученика нет записи о прогрессе.",
                reply_markup=get_mentor_menu_keyboard(),
            )
            return
        except NoStagesFoundError:
            await callback.message.edit_text(
                "❌ Не найдено этапов для направления ученика.",
                reply_markup=get_mentor_menu_keyboard(),
            )
            return
        except Exception as e:
            logger.error("Failed to calculate bulk deadlines", error=str(e))
            await callback.message.edit_text(
                "❌ Не удалось рассчитать дедлайны.",
                reply_markup=get_mentor_menu_keyboard(),
            )
            return

        # Show preview
        student_name = student.first_name
        if student.last_name:
            student_name += f" {student.last_name}"

        preview_text = (
            f"📋 Установка дедлайнов для всех этапов\n\n"
            f"👤 Ученик: {student_name}\n"
            f"📚 Направление: {direction.name}\n\n"
            f"Рассчитанные дедлайны:\n\n"
        )

        for preview in previews:
            deadline_str = preview.calculated_deadline.strftime("%d.%m.%Y")
            preview_text += f"📍 {preview.stage.title}\n"
            preview_text += f"   📅 {deadline_str}\n\n"

        preview_text += "Подтвердите установку дедлайнов:"

        # Store preview data for confirmation
        stage_deadlines = [
            (preview.stage.id, preview.calculated_deadline.isoformat())
            for preview in previews
        ]

        buttons = [
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить",
                    callback_data=f"confirm_bulk:{student_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=f"cancel_bulk:{student_id}"
                ),
            ]
        ]

        await callback.message.edit_text(
            preview_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        )

        await state.update_data(student_id=student_id, stage_deadlines=stage_deadlines)
        await state.set_state(MentorStudentViewStates.confirming_bulk_deadlines)


@router.callback_query(MentorStudentViewStates.confirming_bulk_deadlines, F.data.startswith("confirm_bulk:"))
async def handle_confirm_bulk_deadlines(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle confirmation of bulk deadlines."""
    await callback.answer()

    student_id = int(callback.data.split(":", 1)[1])

    data = await state.get_data()
    stage_deadlines_iso = data.get("stage_deadlines", [])

    if not stage_deadlines_iso:
        await callback.message.edit_text(
            "❌ Ошибка: данные дедлайнов потеряны. Начните заново.",
            reply_markup=get_mentor_menu_keyboard(),
        )
        await state.clear()
        return

    # Convert ISO dates back to date objects
    stage_deadlines = [
        (stage_id, date.fromisoformat(deadline_iso))
        for stage_id, deadline_iso in stage_deadlines_iso
    ]

    async with get_session() as session:
        # Check mentor access
        mentor_service = MentorService(session)
        try:
            await mentor_service.check_mentor_access(callback.from_user.id)
        except MentorNotFoundError:
            await callback.message.edit_text("❌ Доступ запрещён.")
            await state.clear()
            return

        # Set bulk deadlines
        deadline_service = MentorDeadlineService(session)
        try:
            # Get student and stage info
            from sputnik_offer_crm.models import Student, Stage
            from sqlalchemy import select

            result = await session.execute(
                select(Student).where(Student.id == student_id)
            )
            student = result.scalar_one_or_none()

            # Get stage titles for notification
            stage_ids = [stage_id for stage_id, _ in stage_deadlines]
            result = await session.execute(
                select(Stage).where(Stage.id.in_(stage_ids))
            )
            stages_dict = {stage.id: stage for stage in result.scalars().all()}

            count = await deadline_service.set_all_stage_deadlines(
                student_id, stage_deadlines
            )

            await callback.message.edit_text(
                f"✅ Дедлайны успешно установлены!\n\n"
                f"Установлено дедлайнов: {count}"
            )

            logger.info(
                "Bulk deadlines set",
                mentor_id=callback.from_user.id,
                student_id=student_id,
                count=count,
            )

            # Send notification to student
            if student:
                stage_deadline_list = [
                    (stages_dict[stage_id].title, deadline)
                    for stage_id, deadline in stage_deadlines
                    if stage_id in stages_dict
                ]
                notification_service = EventNotificationService()
                await notification_service.notify_bulk_deadlines_set(
                    student=student,
                    stage_deadlines=stage_deadline_list,
                )

            # Show updated card
            await show_student_card(callback.message, student_id)

        except DeadlineStudentNotFoundError:
            await callback.message.edit_text(
                "❌ Ученик не найден.",
                reply_markup=get_mentor_menu_keyboard(),
            )
        except DeadlineStudentHasNoProgressError:
            await callback.message.edit_text(
                "❌ У ученика нет записи о прогрессе.",
                reply_markup=get_mentor_menu_keyboard(),
            )
        except DeadlineManagementError as e:
            logger.error("Failed to set bulk deadlines", error=str(e), exc_info=True)
            await callback.message.edit_text(
                "❌ Не удалось установить дедлайны.",
                reply_markup=get_mentor_menu_keyboard(),
            )
        finally:
            await state.clear()


@router.callback_query(MentorStudentViewStates.confirming_bulk_deadlines, F.data.startswith("cancel_bulk:"))
async def handle_cancel_bulk_deadlines(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle cancellation of bulk deadlines."""
    await callback.answer()

    student_id = int(callback.data.split(":", 1)[1])

    await callback.message.edit_text("❌ Установка дедлайнов отменена.")
    await state.clear()

    # Show card again
    await show_student_card(callback.message, student_id)


@router.callback_query(F.data.startswith("dropout:"))
async def handle_dropout_request(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle request to dropout student."""
    await callback.answer()

    student_id = int(callback.data.split(":", 1)[1])

    async with get_session() as session:
        # Check mentor access
        mentor_service = MentorService(session)
        try:
            await mentor_service.check_mentor_access(callback.from_user.id)
        except MentorNotFoundError:
            await callback.message.edit_text("❌ Доступ запрещён. Вы не являетесь ментором.")
            return

        # Get student info
        from sputnik_offer_crm.models import Student
        from sqlalchemy import select

        result = await session.execute(
            select(Student).where(Student.id == student_id)
        )
        student = result.scalar_one_or_none()

        if not student:
            await callback.message.edit_text(
                "❌ Ученик не найден.",
                reply_markup=get_mentor_menu_keyboard(),
            )
            return

        if not student.is_active:
            await callback.message.edit_text(
                "ℹ️ Ученик уже отчислен.",
                reply_markup=get_mentor_menu_keyboard(),
            )
            return

        # Show confirmation
        student_name = student.first_name
        if student.last_name:
            student_name += f" {student.last_name}"

        confirmation_text = (
            f"❌ Отчисление ученика\n\n"
            f"👤 Ученик: {student_name}\n\n"
            f"⚠️ Внимание:\n"
            f"• Ученик будет отчислен\n"
            f"• Все данные (прогресс, отчёты, задачи) сохранятся\n"
            f"• Ученик не сможет использовать активные функции бота\n\n"
            f"Подтвердите отчисление:"
        )

        buttons = [
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить отчисление",
                    callback_data=f"confirm_dropout:{student_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=f"cancel_dropout:{student_id}"
                ),
            ],
        ]

        await callback.message.edit_text(
            confirmation_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        )

        await state.update_data(student_id=student_id)
        await state.set_state(MentorStudentViewStates.confirming_dropout)


@router.callback_query(MentorStudentViewStates.confirming_dropout, F.data.startswith("confirm_dropout:"))
async def handle_confirm_dropout(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle confirmation of student dropout."""
    await callback.answer()

    student_id = int(callback.data.split(":", 1)[1])

    async with get_session() as session:
        # Check mentor access
        mentor_service = MentorService(session)
        try:
            await mentor_service.check_mentor_access(callback.from_user.id)
        except MentorNotFoundError:
            await callback.message.edit_text("❌ Доступ запрещён.")
            await state.clear()
            return

        # Perform dropout
        status_service = MentorStudentStatusService(session)
        try:
            student = await status_service.dropout_student(student_id)

            student_name = student.first_name
            if student.last_name:
                student_name += f" {student.last_name}"

            await callback.message.edit_text(
                f"✅ Ученик отчислен\n\n"
                f"👤 {student_name}\n\n"
                f"Все данные сохранены."
            )

            logger.info(
                "Student dropped out",
                mentor_id=callback.from_user.id,
                student_id=student_id,
            )

            # Send notification to student
            notification_service = EventNotificationService()
            await notification_service.notify_student_dropped(student=student)

            # Show updated card
            await show_student_card(callback.message, student_id)

        except StatusStudentNotFoundError:
            await callback.message.edit_text(
                "❌ Ученик не найден.",
                reply_markup=get_mentor_menu_keyboard(),
            )
        except StudentAlreadyInactiveError:
            await callback.message.edit_text(
                "ℹ️ Ученик уже отчислен.",
                reply_markup=get_mentor_menu_keyboard(),
            )
        except StudentStatusManagementError as e:
            logger.error("Failed to dropout student", error=str(e), exc_info=True)
            await callback.message.edit_text(
                "❌ Не удалось отчислить ученика.",
                reply_markup=get_mentor_menu_keyboard(),
            )
        finally:
            await state.clear()


@router.callback_query(MentorStudentViewStates.confirming_dropout, F.data.startswith("cancel_dropout:"))
async def handle_cancel_dropout(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle cancellation of student dropout."""
    await callback.answer()

    student_id = int(callback.data.split(":", 1)[1])

    await callback.message.edit_text("❌ Отчисление отменено.")
    await state.clear()

    # Show card again
    await show_student_card(callback.message, student_id)


@router.callback_query(F.data.startswith("offer_completion:"))
async def handle_offer_completion_request(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle request to complete student with offer."""
    await callback.answer()

    student_id = int(callback.data.split(":", 1)[1])

    async with get_session() as session:
        # Check mentor access
        mentor_service = MentorService(session)
        try:
            await mentor_service.check_mentor_access(callback.from_user.id)
        except MentorNotFoundError:
            await callback.message.edit_text("❌ Доступ запрещён. Вы не являетесь ментором.")
            return

        # Get student info
        from sputnik_offer_crm.models import Student
        from sqlalchemy import select

        result = await session.execute(
            select(Student).where(Student.id == student_id)
        )
        student = result.scalar_one_or_none()

        if not student:
            await callback.message.edit_text(
                "❌ Ученик не найден.",
                reply_markup=get_mentor_menu_keyboard(),
            )
            return

        if not student.is_active:
            await callback.message.edit_text(
                "ℹ️ Ученик неактивен (отчислен). Завершение с оффером доступно только для активных учеников.",
                reply_markup=get_mentor_menu_keyboard(),
            )
            return

        if student.offer_received_at is not None:
            offer_date = student.offer_received_at.strftime("%d.%m.%Y")
            await callback.message.edit_text(
                f"ℹ️ Ученик уже завершён с оффером.\n\n"
                f"🏢 Компания: {student.offer_company}\n"
                f"💼 Позиция: {student.offer_position}\n"
                f"📅 Дата получения: {offer_date}",
                reply_markup=get_mentor_menu_keyboard(),
            )
            return

        # Start flow - ask for company
        student_name = student.first_name
        if student.last_name:
            student_name += f" {student.last_name}"

        await callback.message.edit_text(
            f"✅ Завершение с оффером\n\n"
            f"👤 Ученик: {student_name}\n\n"
            f"Введите название компании:"
        )

        await state.update_data(student_id=student_id)
        await state.set_state(MentorStudentViewStates.waiting_for_company)


@router.message(MentorStudentViewStates.waiting_for_company)
async def handle_company_input(message: Message, state: FSMContext) -> None:
    """Handle company name input."""
    if not message.text:
        await message.answer("Пожалуйста, отправьте текстовое сообщение с названием компании.")
        return

    company = message.text.strip()

    if not company:
        await message.answer("Название компании не может быть пустым. Введите название компании:")
        return

    if len(company) > 500:
        await message.answer(
            "Название компании слишком длинное (максимум 500 символов). Введите название компании:"
        )
        return

    # Store company and ask for position
    await state.update_data(company=company)

    await message.answer(
        f"🏢 Компания: {company}\n\n"
        f"Теперь введите название позиции:"
    )

    await state.set_state(MentorStudentViewStates.waiting_for_position)


@router.message(MentorStudentViewStates.waiting_for_position)
async def handle_position_input(message: Message, state: FSMContext) -> None:
    """Handle position title input."""
    if not message.text:
        await message.answer("Пожалуйста, отправьте текстовое сообщение с названием позиции.")
        return

    position = message.text.strip()

    if not position:
        await message.answer("Название позиции не может быть пустым. Введите название позиции:")
        return

    if len(position) > 500:
        await message.answer(
            "Название позиции слишком длинное (максимум 500 символов). Введите название позиции:"
        )
        return

    # Store position and show confirmation
    await state.update_data(position=position)

    data = await state.get_data()
    student_id = data.get("student_id")
    company = data.get("company")

    if not student_id or not company:
        await message.answer(
            "❌ Ошибка: данные сессии потеряны. Начните заново.",
            reply_markup=get_mentor_menu_keyboard(),
        )
        await state.clear()
        return

    # Get student name for confirmation
    async with get_session() as session:
        from sputnik_offer_crm.models import Student
        from sqlalchemy import select

        result = await session.execute(
            select(Student).where(Student.id == student_id)
        )
        student = result.scalar_one_or_none()

        if not student:
            await message.answer(
                "❌ Ученик не найден.",
                reply_markup=get_mentor_menu_keyboard(),
            )
            await state.clear()
            return

        student_name = student.first_name
        if student.last_name:
            student_name += f" {student.last_name}"

        confirmation_text = (
            f"✅ Подтверждение завершения с оффером\n\n"
            f"👤 Ученик: {student_name}\n"
            f"🏢 Компания: {company}\n"
            f"💼 Позиция: {position}\n\n"
            f"Подтвердите завершение:"
        )

        buttons = [
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить",
                    callback_data=f"confirm_offer:{student_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=f"cancel_offer:{student_id}"
                ),
            ],
        ]

        await message.answer(
            confirmation_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        )

        await state.set_state(MentorStudentViewStates.confirming_offer_completion)


@router.callback_query(MentorStudentViewStates.confirming_offer_completion, F.data.startswith("confirm_offer:"))
async def handle_confirm_offer_completion(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle confirmation of offer completion."""
    await callback.answer()

    student_id = int(callback.data.split(":", 1)[1])

    data = await state.get_data()
    company = data.get("company")
    position = data.get("position")

    if not company or not position:
        await callback.message.edit_text(
            "❌ Ошибка: данные оффера потеряны. Начните заново.",
            reply_markup=get_mentor_menu_keyboard(),
        )
        await state.clear()
        return

    async with get_session() as session:
        # Check mentor access
        mentor_service = MentorService(session)
        try:
            await mentor_service.check_mentor_access(callback.from_user.id)
        except MentorNotFoundError:
            await callback.message.edit_text("❌ Доступ запрещён.")
            await state.clear()
            return

        # Complete with offer
        offer_service = MentorOfferCompletionService(session)
        try:
            student = await offer_service.complete_with_offer(
                student_id, company, position
            )

            student_name = student.first_name
            if student.last_name:
                student_name += f" {student.last_name}"

            offer_date = student.offer_received_at.strftime("%d.%m.%Y")

            await callback.message.edit_text(
                f"✅ Ученик успешно завершён с оффером!\n\n"
                f"👤 {student_name}\n"
                f"🏢 Компания: {company}\n"
                f"💼 Позиция: {position}\n"
                f"📅 Дата: {offer_date}\n\n"
                f"Поздравляем с успешным завершением!"
            )

            logger.info(
                "Student completed with offer",
                mentor_id=callback.from_user.id,
                student_id=student_id,
                company=company,
                position=position,
            )

            # Send notification to student
            notification_service = EventNotificationService()
            await notification_service.notify_offer_received(
                student=student,
                company=company,
                position=position,
            )

            # Show updated card
            await show_student_card(callback.message, student_id)

        except OfferCompletionStudentNotFoundError:
            await callback.message.edit_text(
                "❌ Ученик не найден.",
                reply_markup=get_mentor_menu_keyboard(),
            )
        except StudentInactiveError:
            await callback.message.edit_text(
                "❌ Ученик неактивен (отчислен).",
                reply_markup=get_mentor_menu_keyboard(),
            )
        except StudentAlreadyCompletedError:
            await callback.message.edit_text(
                "ℹ️ Ученик уже завершён с оффером.",
                reply_markup=get_mentor_menu_keyboard(),
            )
        except OfferCompletionError as e:
            logger.error("Failed to complete student with offer", error=str(e), exc_info=True)
            await callback.message.edit_text(
                "❌ Не удалось завершить ученика с оффером.",
                reply_markup=get_mentor_menu_keyboard(),
            )
        finally:
            await state.clear()


@router.callback_query(MentorStudentViewStates.confirming_offer_completion, F.data.startswith("cancel_offer:"))
async def handle_cancel_offer_completion(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle cancellation of offer completion."""
    await callback.answer()

    student_id = int(callback.data.split(":", 1)[1])

    await callback.message.edit_text("❌ Завершение с оффером отменено.")
    await state.clear()

    # Show card again
    await show_student_card(callback.message, student_id)


@router.callback_query(F.data.startswith("pause:"))
async def handle_pause_request(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle request to pause student."""
    await callback.answer()

    student_id = int(callback.data.split(":", 1)[1])

    async with get_session() as session:
        # Check mentor access
        mentor_service = MentorService(session)
        try:
            await mentor_service.check_mentor_access(callback.from_user.id)
        except MentorNotFoundError:
            await callback.message.edit_text("❌ Доступ запрещён. Вы не являетесь ментором.")
            return

        # Get student info
        from sputnik_offer_crm.models import Student
        from sqlalchemy import select

        result = await session.execute(
            select(Student).where(Student.id == student_id)
        )
        student = result.scalar_one_or_none()

        if not student:
            await callback.message.edit_text(
                "❌ Ученик не найден.",
                reply_markup=get_mentor_menu_keyboard(),
            )
            return

        if not student.is_active:
            await callback.message.edit_text(
                "ℹ️ Ученик неактивен (отчислен). Постановка на паузу доступна только для активных учеников.",
                reply_markup=get_mentor_menu_keyboard(),
            )
            return

        if student.is_paused:
            await callback.message.edit_text(
                "ℹ️ Ученик уже на паузе.",
                reply_markup=get_mentor_menu_keyboard(),
            )
            return

        # Show confirmation
        student_name = student.first_name
        if student.last_name:
            student_name += f" {student.last_name}"

        confirmation_text = (
            f"⏸ Постановка на паузу\n\n"
            f"👤 Ученик: {student_name}\n\n"
            f"⚠️ Внимание:\n"
            f"• Ученик будет поставлен на паузу\n"
            f"• Все данные (прогресс, отчёты, задачи) сохранятся\n"
            f"• Ученик не сможет отправлять отчёты и использовать активные функции\n"
            f"• Вы сможете возобновить ученика позже\n\n"
            f"Подтвердите постановку на паузу:"
        )

        buttons = [
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить",
                    callback_data=f"confirm_pause:{student_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=f"cancel_pause:{student_id}"
                ),
            ],
        ]

        await callback.message.edit_text(
            confirmation_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        )

        await state.update_data(student_id=student_id)
        await state.set_state(MentorStudentViewStates.confirming_pause)


@router.callback_query(MentorStudentViewStates.confirming_pause, F.data.startswith("confirm_pause:"))
async def handle_confirm_pause(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle confirmation of student pause."""
    await callback.answer()

    student_id = int(callback.data.split(":", 1)[1])

    async with get_session() as session:
        # Check mentor access
        mentor_service = MentorService(session)
        try:
            await mentor_service.check_mentor_access(callback.from_user.id)
        except MentorNotFoundError:
            await callback.message.edit_text("❌ Доступ запрещён.")
            await state.clear()
            return

        # Perform pause
        pause_service = MentorPauseResumeService(session)
        try:
            student = await pause_service.pause_student(student_id)

            student_name = student.first_name
            if student.last_name:
                student_name += f" {student.last_name}"

            await callback.message.edit_text(
                f"⏸ Ученик поставлен на паузу\n\n"
                f"👤 {student_name}\n\n"
                f"Все данные сохранены. Вы можете возобновить ученика позже."
            )

            logger.info(
                "Student paused",
                mentor_id=callback.from_user.id,
                student_id=student_id,
            )

            # Send notification to student
            notification_service = EventNotificationService()
            await notification_service.notify_student_paused(student=student)

            # Show updated card
            await show_student_card(callback.message, student_id)

        except PauseResumeStudentNotFoundError:
            await callback.message.edit_text(
                "❌ Ученик не найден.",
                reply_markup=get_mentor_menu_keyboard(),
            )
        except PauseResumeStudentInactiveError:
            await callback.message.edit_text(
                "❌ Ученик неактивен (отчислен).",
                reply_markup=get_mentor_menu_keyboard(),
            )
        except StudentAlreadyPausedError:
            await callback.message.edit_text(
                "ℹ️ Ученик уже на паузе.",
                reply_markup=get_mentor_menu_keyboard(),
            )
        except PauseResumeError as e:
            logger.error("Failed to pause student", error=str(e), exc_info=True)
            await callback.message.edit_text(
                "❌ Не удалось поставить ученика на паузу.",
                reply_markup=get_mentor_menu_keyboard(),
            )
        finally:
            await state.clear()


@router.callback_query(MentorStudentViewStates.confirming_pause, F.data.startswith("cancel_pause:"))
async def handle_cancel_pause(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle cancellation of student pause."""
    await callback.answer()

    student_id = int(callback.data.split(":", 1)[1])

    await callback.message.edit_text("❌ Постановка на паузу отменена.")
    await state.clear()

    # Show card again
    await show_student_card(callback.message, student_id)


@router.callback_query(F.data.startswith("resume:"))
async def handle_resume_request(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle request to resume student."""
    await callback.answer()

    student_id = int(callback.data.split(":", 1)[1])

    async with get_session() as session:
        # Check mentor access
        mentor_service = MentorService(session)
        try:
            await mentor_service.check_mentor_access(callback.from_user.id)
        except MentorNotFoundError:
            await callback.message.edit_text("❌ Доступ запрещён. Вы не являетесь ментором.")
            return

        # Get student info
        from sputnik_offer_crm.models import Student
        from sqlalchemy import select

        result = await session.execute(
            select(Student).where(Student.id == student_id)
        )
        student = result.scalar_one_or_none()

        if not student:
            await callback.message.edit_text(
                "❌ Ученик не найден.",
                reply_markup=get_mentor_menu_keyboard(),
            )
            return

        if not student.is_active:
            await callback.message.edit_text(
                "ℹ️ Ученик неактивен (отчислен). Возобновление доступно только для активных учеников.",
                reply_markup=get_mentor_menu_keyboard(),
            )
            return

        if not student.is_paused:
            await callback.message.edit_text(
                "ℹ️ Ученик не на паузе.",
                reply_markup=get_mentor_menu_keyboard(),
            )
            return

        # Show confirmation
        student_name = student.first_name
        if student.last_name:
            student_name += f" {student.last_name}"

        confirmation_text = (
            f"▶️ Возобновление ученика\n\n"
            f"👤 Ученик: {student_name}\n\n"
            f"Ученик будет возобновлён и сможет снова использовать активные функции бота.\n\n"
            f"Подтвердите возобновление:"
        )

        buttons = [
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить",
                    callback_data=f"confirm_resume:{student_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=f"cancel_resume:{student_id}"
                ),
            ],
        ]

        await callback.message.edit_text(
            confirmation_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        )

        await state.update_data(student_id=student_id)
        await state.set_state(MentorStudentViewStates.confirming_resume)


@router.callback_query(MentorStudentViewStates.confirming_resume, F.data.startswith("confirm_resume:"))
async def handle_confirm_resume(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle confirmation of student resume."""
    await callback.answer()

    student_id = int(callback.data.split(":", 1)[1])

    async with get_session() as session:
        # Check mentor access
        mentor_service = MentorService(session)
        try:
            await mentor_service.check_mentor_access(callback.from_user.id)
        except MentorNotFoundError:
            await callback.message.edit_text("❌ Доступ запрещён.")
            await state.clear()
            return

        # Perform resume
        pause_service = MentorPauseResumeService(session)
        try:
            student = await pause_service.resume_student(student_id)

            student_name = student.first_name
            if student.last_name:
                student_name += f" {student.last_name}"

            await callback.message.edit_text(
                f"▶️ Ученик возобновлён\n\n"
                f"👤 {student_name}\n\n"
                f"Ученик снова может использовать активные функции бота."
            )

            logger.info(
                "Student resumed",
                mentor_id=callback.from_user.id,
                student_id=student_id,
            )

            # Send notification to student
            notification_service = EventNotificationService()
            await notification_service.notify_student_resumed(student=student)

            # Show updated card
            await show_student_card(callback.message, student_id)

        except PauseResumeStudentNotFoundError:
            await callback.message.edit_text(
                "❌ Ученик не найден.",
                reply_markup=get_mentor_menu_keyboard(),
            )
        except PauseResumeStudentInactiveError:
            await callback.message.edit_text(
                "❌ Ученик неактивен (отчислен).",
                reply_markup=get_mentor_menu_keyboard(),
            )
        except StudentNotPausedError:
            await callback.message.edit_text(
                "ℹ️ Ученик не на паузе.",
                reply_markup=get_mentor_menu_keyboard(),
            )
        except PauseResumeError as e:
            logger.error("Failed to resume student", error=str(e), exc_info=True)
            await callback.message.edit_text(
                "❌ Не удалось возобновить ученика.",
                reply_markup=get_mentor_menu_keyboard(),
            )
        finally:
            await state.clear()


@router.callback_query(MentorStudentViewStates.confirming_resume, F.data.startswith("cancel_resume:"))
async def handle_cancel_resume(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle cancellation of student resume."""
    await callback.answer()

    student_id = int(callback.data.split(":", 1)[1])

    await callback.message.edit_text("❌ Возобновление отменено.")
    await state.clear()

    # Show card again
    await show_student_card(callback.message, student_id)


# Task creation handlers


@router.callback_query(F.data.startswith("add_task:"))
async def handle_add_task_request(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle request to add task to student."""
    await callback.answer()

    student_id = int(callback.data.split(":", 1)[1])

    async with get_session() as session:
        # Check mentor access
        mentor_service = MentorService(session)
        try:
            await mentor_service.check_mentor_access(callback.from_user.id)
        except MentorNotFoundError:
            await callback.message.edit_text("❌ Доступ запрещён. Вы не являетесь ментором.")
            return

    # Save student_id to state
    await state.update_data(student_id=student_id)
    await state.set_state(MentorTaskCreationStates.waiting_for_title)

    await callback.message.edit_text(
        "📌 Создание задачи\n\n"
        "Введите название задачи:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel_add_task:{student_id}")]
        ]),
    )


@router.message(MentorTaskCreationStates.waiting_for_title)
async def handle_task_title_input(message: Message, state: FSMContext) -> None:
    """Handle task title input."""
    title = message.text.strip()

    if not title:
        await message.answer("❌ Название задачи не может быть пустым. Попробуйте ещё раз:")
        return

    # Save title
    await state.update_data(title=title)
    await state.set_state(MentorTaskCreationStates.waiting_for_description)

    data = await state.get_data()
    student_id = data["student_id"]

    await message.answer(
        f"✅ Название: {title}\n\n"
        "Введите описание задачи или нажмите 'Пропустить':",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_task_description")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel_add_task:{student_id}")]
        ]),
    )


@router.callback_query(MentorTaskCreationStates.waiting_for_description, F.data == "skip_task_description")
async def handle_skip_task_description(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle skipping task description."""
    await callback.answer()

    await state.update_data(description=None)
    await state.set_state(MentorTaskCreationStates.waiting_for_deadline)

    data = await state.get_data()
    student_id = data["student_id"]

    await callback.message.edit_text(
        "Введите дедлайн в формате ДД.ММ.ГГГГ или нажмите 'Пропустить':",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_task_deadline")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel_add_task:{student_id}")]
        ]),
    )


@router.message(MentorTaskCreationStates.waiting_for_description)
async def handle_task_description_input(message: Message, state: FSMContext) -> None:
    """Handle task description input."""
    description = message.text.strip()

    await state.update_data(description=description)
    await state.set_state(MentorTaskCreationStates.waiting_for_deadline)

    data = await state.get_data()
    student_id = data["student_id"]

    await message.answer(
        "✅ Описание сохранено\n\n"
        "Введите дедлайн в формате ДД.ММ.ГГГГ или нажмите 'Пропустить':",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_task_deadline")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel_add_task:{student_id}")]
        ]),
    )


@router.callback_query(MentorTaskCreationStates.waiting_for_deadline, F.data == "skip_task_deadline")
async def handle_skip_task_deadline(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle skipping task deadline."""
    await callback.answer()

    await state.update_data(deadline=None)
    await state.set_state(MentorTaskCreationStates.waiting_for_mentor_task)

    data = await state.get_data()
    student_id = data["student_id"]

    await callback.message.edit_text(
        "Введите заметку для себя (mentor_task) или нажмите 'Пропустить':",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_mentor_task")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel_add_task:{student_id}")]
        ]),
    )


@router.message(MentorTaskCreationStates.waiting_for_deadline)
async def handle_task_deadline_input(message: Message, state: FSMContext) -> None:
    """Handle task deadline input."""
    deadline_str = message.text.strip()

    # Parse deadline
    try:
        day, month, year = deadline_str.split(".")
        deadline = date(int(year), int(month), int(day))
    except (ValueError, AttributeError):
        await message.answer(
            "❌ Неверный формат даты. Используйте формат ДД.ММ.ГГГГ (например, 25.12.2026):"
        )
        return

    await state.update_data(deadline=deadline)
    await state.set_state(MentorTaskCreationStates.waiting_for_mentor_task)

    data = await state.get_data()
    student_id = data["student_id"]

    await message.answer(
        f"✅ Дедлайн: {deadline.strftime('%d.%m.%Y')}\n\n"
        "Введите заметку для себя (mentor_task) или нажмите 'Пропустить':",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_mentor_task")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel_add_task:{student_id}")]
        ]),
    )


@router.callback_query(MentorTaskCreationStates.waiting_for_mentor_task, F.data == "skip_mentor_task")
async def handle_skip_mentor_task(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle skipping mentor task."""
    await callback.answer()

    await state.update_data(mentor_task=None)
    await show_task_confirmation(callback.message, state)


@router.message(MentorTaskCreationStates.waiting_for_mentor_task)
async def handle_mentor_task_input(message: Message, state: FSMContext) -> None:
    """Handle mentor task input."""
    mentor_task = message.text.strip()

    await state.update_data(mentor_task=mentor_task)
    await show_task_confirmation(message, state)


async def show_task_confirmation(message: Message, state: FSMContext) -> None:
    """Show task confirmation."""
    data = await state.get_data()
    student_id = data["student_id"]
    title = data["title"]
    description = data.get("description")
    deadline = data.get("deadline")
    mentor_task = data.get("mentor_task")

    lines = ["📌 Подтверждение создания задачи\n"]
    lines.append(f"📝 Название: {title}")
    if description:
        lines.append(f"📄 Описание: {description}")
    if deadline:
        lines.append(f"📅 Дедлайн: {deadline.strftime('%d.%m.%Y')}")
    if mentor_task:
        lines.append(f"📋 Заметка: {mentor_task}")

    await state.set_state(MentorTaskCreationStates.confirming_task)

    await message.answer(
        "\n".join(lines) + "\n\nСоздать задачу?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Создать", callback_data="confirm_add_task"),
                InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel_add_task:{student_id}")
            ]
        ]),
    )


@router.callback_query(MentorTaskCreationStates.confirming_task, F.data == "confirm_add_task")
async def handle_confirm_add_task(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle task creation confirmation."""
    await callback.answer()

    data = await state.get_data()
    student_id = data["student_id"]
    title = data["title"]
    description = data.get("description")
    deadline = data.get("deadline")
    mentor_task = data.get("mentor_task")

    async with get_session() as session:
        from sputnik_offer_crm.services.student_task import StudentTaskService, StudentNotFoundError

        service = StudentTaskService(session)
        try:
            task = await service.create_task(
                student_id=student_id,
                title=title,
                description=description,
                deadline=deadline,
                mentor_task=mentor_task,
            )

            await callback.message.edit_text(
                f"✅ Задача создана\n\n"
                f"📝 {task.title}\n"
                f"🆔 ID: {task.id}"
            )

            logger.info(
                "Mentor created task",
                mentor_id=callback.from_user.id,
                student_id=student_id,
                task_id=task.id,
            )

        except StudentNotFoundError:
            await callback.message.edit_text("❌ Ученик не найден.")
        except Exception as e:
            logger.error("Failed to create task", error=str(e), exc_info=True)
            await callback.message.edit_text("❌ Не удалось создать задачу.")
        finally:
            await state.clear()

    # Show card again
    await show_student_card(callback.message, student_id)


@router.callback_query(F.data.startswith("cancel_add_task:"))
async def handle_cancel_add_task(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle cancellation of task creation."""
    await callback.answer()

    student_id = int(callback.data.split(":", 1)[1])

    await callback.message.edit_text("❌ Создание задачи отменено.")
    await state.clear()

    # Show card again
    await show_student_card(callback.message, student_id)


@router.callback_query(F.data.startswith("view_student_tasks:"))
async def handle_view_student_tasks(callback: CallbackQuery) -> None:
    """Handle viewing student tasks."""
    await callback.answer()

    student_id = int(callback.data.split(":", 1)[1])

    async with get_session() as session:
        # Check mentor access
        mentor_service = MentorService(session)
        try:
            await mentor_service.check_mentor_access(callback.from_user.id)
        except MentorNotFoundError:
            await callback.message.edit_text("❌ Доступ запрещён. Вы не являетесь ментором.")
            return

        from sputnik_offer_crm.services.student_task import StudentTaskService, StudentNotFoundError

        service = StudentTaskService(session)
        try:
            tasks = await service.get_student_tasks(student_id)

            if not tasks:
                await callback.message.edit_text(
                    "📋 У ученика пока нет задач.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"back_to_card:{student_id}")]
                    ]),
                )
                return

            # Build tasks list with cancel buttons
            lines = ["📋 Задачи ученика\n"]
            buttons = []

            for i, task in enumerate(tasks, 1):
                lines.append(f"{i}. {task.title}")

                # Status emoji
                if task.status == "done":
                    status_emoji = "✅"
                    status_text = "Выполнена"
                elif task.status == "cancelled":
                    status_emoji = "❌"
                    status_text = "Отменена"
                elif task.status == "overdue":
                    status_emoji = "⚠️"
                    status_text = "Просрочена"
                else:  # open
                    status_emoji = "📌"
                    status_text = "Открыта"

                lines.append(f"   {status_emoji} Статус: {status_text}")

                if task.deadline:
                    deadline_str = task.deadline.strftime("%d.%m.%Y")
                    lines.append(f"   📅 Дедлайн: {deadline_str}")

                if task.description:
                    desc = task.description
                    if len(desc) > 100:
                        desc = desc[:100] + "..."
                    lines.append(f"   📄 {desc}")

                if task.mentor_task:
                    mentor_note = task.mentor_task
                    if len(mentor_note) > 100:
                        mentor_note = mentor_note[:100] + "..."
                    lines.append(f"   📋 Заметка: {mentor_note}")

                # Add cancel button for open tasks
                if task.status == "open":
                    buttons.append([
                        InlineKeyboardButton(
                            text=f"❌ Отменить #{i}",
                            callback_data=f"cancel_student_task:{task.id}:{student_id}"
                        )
                    ])

                lines.append("")

            # Add back button
            buttons.append([
                InlineKeyboardButton(text="◀️ Назад", callback_data=f"back_to_card:{student_id}")
            ])

            await callback.message.edit_text(
                "\n".join(lines),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            )

            logger.info(
                "Mentor viewed student tasks",
                mentor_id=callback.from_user.id,
                student_id=student_id,
                tasks_count=len(tasks),
            )

        except StudentNotFoundError:
            await callback.message.edit_text("❌ Ученик не найден.")
        except Exception as e:
            logger.error("Failed to get student tasks", error=str(e), exc_info=True)
            await callback.message.edit_text("❌ Не удалось загрузить задачи.")


@router.callback_query(F.data.startswith("cancel_student_task:"))
async def handle_cancel_student_task(callback: CallbackQuery) -> None:
    """Handle cancelling student task."""
    await callback.answer()

    parts = callback.data.split(":", 2)
    task_id = int(parts[1])
    student_id = int(parts[2])

    async with get_session() as session:
        # Check mentor access
        mentor_service = MentorService(session)
        try:
            await mentor_service.check_mentor_access(callback.from_user.id)
        except MentorNotFoundError:
            await callback.message.edit_text("❌ Доступ запрещён. Вы не являетесь ментором.")
            return

        from sputnik_offer_crm.services.student_task import (
            StudentTaskService,
            TaskNotFoundError,
            TaskAlreadyCancelledError,
            InvalidTaskTransitionError,
        )

        service = StudentTaskService(session)
        try:
            task = await service.cancel_task(task_id)

            await callback.message.edit_text(
                f"✅ Задача отменена\n\n"
                f"📝 {task.title}"
            )

            logger.info(
                "Mentor cancelled task",
                mentor_id=callback.from_user.id,
                task_id=task_id,
                student_id=student_id,
            )

        except TaskNotFoundError:
            await callback.message.edit_text("❌ Задача не найдена.")
        except TaskAlreadyCancelledError:
            await callback.message.edit_text("ℹ️ Эта задача уже отменена.")
        except InvalidTaskTransitionError:
            await callback.message.edit_text("❌ Невозможно отменить выполненную задачу.")
        except Exception as e:
            logger.error("Failed to cancel task", error=str(e), exc_info=True)
            await callback.message.edit_text("❌ Не удалось отменить задачу.")

    # Show tasks list again
    await handle_view_student_tasks(callback)


@router.callback_query(F.data.startswith("back_to_card:"))
async def handle_back_to_card(callback: CallbackQuery) -> None:
    """Handle back to student card."""
    await callback.answer()

    student_id = int(callback.data.split(":", 1)[1])
    await show_student_card(callback.message, student_id)


# Weekly reports handlers


@router.callback_query(F.data.startswith("view_student_reports:"))
async def handle_view_student_reports(callback: CallbackQuery) -> None:
    """Handle viewing student weekly reports."""
    await callback.answer()

    student_id = int(callback.data.split(":", 1)[1])

    async with get_session() as session:
        # Check mentor access
        mentor_service = MentorService(session)
        try:
            await mentor_service.check_mentor_access(callback.from_user.id)
        except MentorNotFoundError:
            await callback.message.edit_text("❌ Доступ запрещён. Вы не являетесь ментором.")
            return

        from sputnik_offer_crm.services.mentor_weekly_reports import (
            MentorWeeklyReportsService,
            StudentNotFoundError,
        )

        service = MentorWeeklyReportsService(session)
        try:
            reports = await service.get_student_reports(student_id, limit=10)

            if not reports:
                await callback.message.edit_text(
                    "📝 У ученика пока нет отчётов.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"back_to_card:{student_id}")]
                    ]),
                )
                return

            # Build reports list
            lines = ["📝 Отчёты ученика\n"]
            buttons = []

            for i, report in enumerate(reports, 1):
                week_str = report.week_start_date.strftime("%d.%m.%Y")
                problem_indicator = " ⚠️" if report.has_problems_unsolved else ""
                lines.append(f"{i}. Неделя с {week_str}{problem_indicator}")

                buttons.append([
                    InlineKeyboardButton(
                        text=f"📄 Открыть #{i}",
                        callback_data=f"open_report:{report.id}:{student_id}"
                    )
                ])

            lines.append("")
            if len(reports) == 10:
                lines.append("(показаны последние 10 отчётов)")

            # Add back button
            buttons.append([
                InlineKeyboardButton(text="◀️ Назад", callback_data=f"back_to_card:{student_id}")
            ])

            await callback.message.edit_text(
                "\n".join(lines),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            )

            logger.info(
                "Mentor viewed student reports list",
                mentor_id=callback.from_user.id,
                student_id=student_id,
                reports_count=len(reports),
            )

        except StudentNotFoundError:
            await callback.message.edit_text("❌ Ученик не найден.")
        except Exception as e:
            logger.error("Failed to get student reports", error=str(e), exc_info=True)
            await callback.message.edit_text("❌ Не удалось загрузить отчёты.")


@router.callback_query(F.data.startswith("open_report:"))
async def handle_open_report(callback: CallbackQuery) -> None:
    """Handle opening full report."""
    await callback.answer()

    parts = callback.data.split(":", 2)
    report_id = int(parts[1])
    student_id = int(parts[2])

    async with get_session() as session:
        # Check mentor access
        mentor_service = MentorService(session)
        try:
            await mentor_service.check_mentor_access(callback.from_user.id)
        except MentorNotFoundError:
            await callback.message.edit_text("❌ Доступ запрещён. Вы не являетесь ментором.")
            return

        from sputnik_offer_crm.services.mentor_weekly_reports import (
            MentorWeeklyReportsService,
            ReportNotFoundError,
        )

        service = MentorWeeklyReportsService(session)
        try:
            report = await service.get_report_detail(report_id)

            # Build report text
            lines = ["📝 Еженедельный отчёт\n"]
            lines.append(f"👤 Ученик: {report.student_name}")
            lines.append(f"📅 Неделя с {report.week_start_date.strftime('%d.%m.%Y')}\n")

            lines.append("❓ Что делали на прошлой неделе?")
            lines.append(report.answer_what_did)
            lines.append("")

            if report.answer_problems_solved:
                lines.append("✅ Какие проблемы решили?")
                lines.append(report.answer_problems_solved)
                lines.append("")

            if report.answer_problems_unsolved:
                lines.append("⚠️ Какие проблемы не решены?")
                lines.append(report.answer_problems_unsolved)
                lines.append("")

            await callback.message.edit_text(
                "\n".join(lines),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ К списку отчётов", callback_data=f"view_student_reports:{student_id}")]
                ]),
            )

            logger.info(
                "Mentor viewed report detail",
                mentor_id=callback.from_user.id,
                report_id=report_id,
                student_id=student_id,
            )

        except ReportNotFoundError:
            await callback.message.edit_text("❌ Отчёт не найден.")
        except Exception as e:
            logger.error("Failed to get report detail", error=str(e), exc_info=True)
            await callback.message.edit_text("❌ Не удалось загрузить отчёт.")


@router.message(F.text == "📝 Последние отчёты")
async def handle_recent_reports(message: Message) -> None:
    """Handle recent reports view request."""
    async with get_session() as session:
        # Check mentor access
        mentor_service = MentorService(session)
        try:
            await mentor_service.check_mentor_access(message.from_user.id)
        except MentorNotFoundError:
            await message.answer("❌ Доступ запрещён. Вы не являетесь ментором.")
            return

        from sputnik_offer_crm.services.mentor_weekly_reports import MentorWeeklyReportsService

        service = MentorWeeklyReportsService(session)
        try:
            reports = await service.get_recent_reports(limit=15)

            if not reports:
                await message.answer(
                    "📝 Пока нет отчётов от учеников.",
                    reply_markup=get_mentor_menu_keyboard(),
                )
                return

            # Build reports list
            lines = ["📝 Последние отчёты учеников\n"]
            buttons = []

            for i, report in enumerate(reports, 1):
                week_str = report.week_start_date.strftime("%d.%m.%Y")
                problem_indicator = " ⚠️" if report.has_problems_unsolved else ""
                lines.append(f"{i}. {report.student_name} — {week_str}{problem_indicator}")

                buttons.append([
                    InlineKeyboardButton(
                        text=f"📄 Открыть #{i}",
                        callback_data=f"open_recent_report:{report.id}"
                    )
                ])

            lines.append("")
            if len(reports) == 15:
                lines.append("(показаны последние 15 отчётов)")

            await message.answer(
                "\n".join(lines),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            )

            logger.info(
                "Mentor viewed recent reports",
                mentor_id=message.from_user.id,
                reports_count=len(reports),
            )

        except Exception as e:
            logger.error("Failed to get recent reports", error=str(e), exc_info=True)
            await message.answer(
                "❌ Не удалось загрузить отчёты.",
                reply_markup=get_mentor_menu_keyboard(),
            )


@router.callback_query(F.data.startswith("open_recent_report:"))
async def handle_open_recent_report(callback: CallbackQuery) -> None:
    """Handle opening report from recent list."""
    await callback.answer()

    report_id = int(callback.data.split(":", 1)[1])

    async with get_session() as session:
        # Check mentor access
        mentor_service = MentorService(session)
        try:
            await mentor_service.check_mentor_access(callback.from_user.id)
        except MentorNotFoundError:
            await callback.message.edit_text("❌ Доступ запрещён. Вы не являетесь ментором.")
            return

        from sputnik_offer_crm.services.mentor_weekly_reports import (
            MentorWeeklyReportsService,
            ReportNotFoundError,
        )

        service = MentorWeeklyReportsService(session)
        try:
            report = await service.get_report_detail(report_id)

            # Build report text
            lines = ["📝 Еженедельный отчёт\n"]
            lines.append(f"👤 Ученик: {report.student_name}")
            lines.append(f"📅 Неделя с {report.week_start_date.strftime('%d.%m.%Y')}\n")

            lines.append("❓ Что делали на прошлой неделе?")
            lines.append(report.answer_what_did)
            lines.append("")

            if report.answer_problems_solved:
                lines.append("✅ Какие проблемы решили?")
                lines.append(report.answer_problems_solved)
                lines.append("")

            if report.answer_problems_unsolved:
                lines.append("⚠️ Какие проблемы не решены?")
                lines.append(report.answer_problems_unsolved)
                lines.append("")

            await callback.message.edit_text("\n".join(lines))

            logger.info(
                "Mentor viewed recent report detail",
                mentor_id=callback.from_user.id,
                report_id=report_id,
            )

        except ReportNotFoundError:
            await callback.message.edit_text("❌ Отчёт не найден.")
        except Exception as e:
            logger.error("Failed to get report detail", error=str(e), exc_info=True)
            await callback.message.edit_text("❌ Не удалось загрузить отчёт.")


@router.callback_query(F.data.startswith("detailed_progress:"))
async def handle_detailed_progress(callback: CallbackQuery) -> None:
    """Handle detailed progress view."""
    await callback.answer()

    student_id = int(callback.data.split(":", 1)[1])

    async with get_session() as session:
        # Check mentor access
        mentor_service = MentorService(session)
        try:
            await mentor_service.check_mentor_access(callback.from_user.id)
        except MentorNotFoundError:
            await callback.message.edit_text("❌ Доступ запрещён. Вы не являетесь ментором.")
            return

        service = MentorStudentService(session)
        detailed = await service.get_detailed_progress(student_id)

        if not detailed:
            await callback.message.edit_text(
                "❌ Информация об ученике не найдена.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад", callback_data=f"back_to_card:{student_id}")]
                ]),
            )
            return

        # Build detailed progress text
        lines = ["📊 Прогресс детальный\n"]

        # Basic info
        lines.append("👤 Информация об ученике")
        lines.append(f"📛 Имя: {detailed.student.first_name}")
        if detailed.student.last_name:
            lines.append(f"   Фамилия: {detailed.student.last_name}")
        if detailed.student.username:
            lines.append(f"💬 Username: @{detailed.student.username}")
        lines.append(f"🌍 Часовой пояс: {detailed.student.timezone}")
        lines.append("")

        # Status
        if not detailed.student.is_active:
            status_text = "⏸ Неактивен (отчислен)"
        elif detailed.student.is_paused:
            status_text = "⏸ На паузе"
        elif detailed.student.offer_received_at:
            status_text = "🎉 Завершён с оффером"
        else:
            status_text = "✅ Активен"
        lines.append(f"Статус: {status_text}")
        lines.append("")

        # Offer info if completed
        if detailed.student.offer_received_at:
            lines.append("🎉 Информация об оффере:")
            lines.append(f"🏢 Компания: {detailed.student.offer_company}")
            lines.append(f"💼 Позиция: {detailed.student.offer_position}")
            offer_date = detailed.student.offer_received_at.strftime("%d.%m.%Y")
            lines.append(f"📅 Дата получения: {offer_date}")
            lines.append("")

        # Direction and progress
        lines.append("📚 Обучение")
        lines.append(f"Направление: {detailed.direction.name}")
        lines.append(f"📍 Текущий этап: {detailed.current_stage.title}")
        started_date = detailed.progress.started_at.strftime("%d.%m.%Y")
        lines.append(f"📅 Дата старта: {started_date}")
        lines.append(f"✅ Пройдено: {detailed.completed_stages_count} из {detailed.total_stages_count} этапов")
        lines.append("")

        # Stages overview
        lines.append("📋 Этапы направления:")
        for stage, status, deadline in detailed.all_stages:
            if status == "completed":
                status_emoji = "✅"
                status_text = "Пройден"
            elif status == "current":
                status_emoji = "📍"
                status_text = "Текущий"
            else:
                status_emoji = "⏳"
                status_text = "Предстоящий"

            lines.append(f"{status_emoji} {stage.title} ({status_text})")
            if deadline:
                date_str = deadline.strftime("%d.%m.%Y")
                lines.append(f"   📅 Дедлайн: {date_str}")

        lines.append("")

        # Tasks summary
        total_tasks = sum(detailed.tasks_summary.values())
        if total_tasks > 0:
            lines.append("📌 Задачи:")
            if detailed.tasks_summary["open"] > 0:
                lines.append(f"   📌 Открыто: {detailed.tasks_summary['open']}")
            if detailed.tasks_summary["done"] > 0:
                lines.append(f"   ✅ Выполнено: {detailed.tasks_summary['done']}")
            if detailed.tasks_summary["cancelled"] > 0:
                lines.append(f"   ❌ Отменено: {detailed.tasks_summary['cancelled']}")
            if detailed.tasks_summary["overdue"] > 0:
                lines.append(f"   ⚠️ Просрочено: {detailed.tasks_summary['overdue']}")
        else:
            lines.append("📌 Задачи: нет")

        lines.append("")

        # Reports summary
        if detailed.recent_reports_count > 0:
            lines.append(f"📝 Отчёты: {detailed.recent_reports_count} шт.")
        else:
            lines.append("📝 Отчёты: пока не отправлялись")

        # Back button
        buttons = [
            [InlineKeyboardButton(text="◀️ К карточке ученика", callback_data=f"back_to_card:{student_id}")]
        ]

        await callback.message.edit_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        )

        logger.info(
            "Mentor viewed detailed progress",
            mentor_id=callback.from_user.id,
            student_id=student_id,
        )
