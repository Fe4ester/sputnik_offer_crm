"""Registration handlers."""

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from sputnik_offer_crm.bot.keyboards import (
    get_other_timezone_keyboard,
    get_timezone_confirmation_keyboard,
    get_timezone_keyboard,
)
from sputnik_offer_crm.bot.states import RegistrationStates
from sputnik_offer_crm.db import get_session
from sputnik_offer_crm.services import (
    DirectionHasNoStagesError,
    InviteCodeAlreadyUsedError,
    InviteCodeNotFoundError,
    RegistrationService,
)
from sputnik_offer_crm.utils.logging import get_logger
from sputnik_offer_crm.utils.timezone import detect_timezone_from_local_time

router = Router(name="registration")
logger = get_logger(__name__)


async def show_student_menu(message: Message) -> None:
    """Show main menu for registered student (temporary entry point)."""
    await message.answer(
        "📚 Главное меню\n\n"
        "Вы зарегистрированы в системе.\n"
        "Функционал кабинета ученика будет доступен в следующих версиях."
    )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, command: CommandObject) -> None:
    """Handle /start command with role-based routing."""
    async with get_session() as session:
        from sputnik_offer_crm.services import MentorService

        # Check if user is a mentor
        mentor_service = MentorService(session)
        mentor = await mentor_service.get_mentor(message.from_user.id)

        if mentor and mentor.is_active:
            # User is a mentor - show mentor menu
            from sputnik_offer_crm.bot.handlers.mentor import show_mentor_menu
            await show_mentor_menu(message)
            await state.clear()
            return

        # Check if user is a student
        student_service = RegistrationService(session)
        existing_student = await student_service.check_student_exists(message.from_user.id)

        if existing_student:
            # User is a student - show student menu
            await show_student_menu(message)
            await state.clear()
            return

    # User is a guest - start registration flow
    if command.args:
        invite_code = command.args.strip()
        await process_invite_code(message, state, invite_code)
    else:
        await message.answer(
            "👋 Добро пожаловать!\n\n"
            "Для регистрации введите код приглашения, который вы получили от ментора."
        )
        await state.set_state(RegistrationStates.waiting_for_code)


@router.message(RegistrationStates.waiting_for_code)
async def handle_invite_code_input(message: Message, state: FSMContext) -> None:
    """Handle invite code input."""
    invite_code = message.text.strip()
    await process_invite_code(message, state, invite_code)


async def process_invite_code(
    message: Message, state: FSMContext, invite_code: str
) -> None:
    """Process and validate invite code."""
    async with get_session() as session:
        service = RegistrationService(session)

        try:
            validated_code = await service.validate_invite_code(invite_code)
        except InviteCodeNotFoundError:
            await message.answer(
                "❌ Код не найден.\n\n"
                "Проверьте правильность кода и попробуйте снова."
            )
            return
        except InviteCodeAlreadyUsedError:
            await message.answer(
                "❌ Этот код уже был использован.\n\n"
                "Обратитесь к ментору за новым кодом."
            )
            return

        # Store invite code string in FSM data
        await state.update_data(invite_code_str=invite_code)

        # Ask for timezone
        await message.answer(
            "✅ Код принят!\n\n"
            "Выберите ваш часовой пояс:",
            reply_markup=get_timezone_keyboard(),
        )
        await state.set_state(RegistrationStates.waiting_for_timezone)


@router.callback_query(
    RegistrationStates.waiting_for_timezone, F.data.startswith("tz:")
)
async def handle_timezone_selection(
    callback: CallbackQuery, state: FSMContext
) -> None:
    """Handle timezone selection."""
    await callback.answer()

    timezone_data = callback.data.split(":", 1)[1]

    if timezone_data == "other":
        await callback.message.edit_text(
            "🌍 Выберите часовой пояс:\n\n"
            "Вы можете:\n"
            "• Выбрать UTC смещение кнопками\n"
            "• Нажать «⏰ Ввести своё время» и отправить текущее время в формате HH:MM",
            reply_markup=get_other_timezone_keyboard(),
        )
        return

    if timezone_data == "back":
        await callback.message.edit_text(
            "Выберите ваш часовой пояс:",
            reply_markup=get_timezone_keyboard(),
        )
        return

    if timezone_data == "input_time":
        await callback.message.edit_text(
            "⏰ Введите ваше текущее локальное время в формате HH:MM\n\n"
            "Например: 15:30\n\n"
            "Бот определит ваш часовой пояс по разнице с UTC."
        )
        await state.set_state(RegistrationStates.waiting_for_local_time)
        return

    # Direct timezone selection - complete registration
    await complete_registration(callback, state, timezone_data)


@router.message(RegistrationStates.waiting_for_local_time)
async def handle_local_time_input(message: Message, state: FSMContext) -> None:
    """Handle local time input for timezone detection."""
    local_time_str = message.text.strip()

    # Detect timezone from local time
    detection_result = detect_timezone_from_local_time(local_time_str)

    if not detection_result:
        await message.answer(
            "❌ Неверный формат времени.\n\n"
            "Пожалуйста, введите время в формате HH:MM (например: 15:30)\n"
            "Или вернитесь назад и выберите часовой пояс кнопками."
        )
        return

    # Store detected timezone and ask for confirmation
    await state.update_data(detected_timezone=detection_result.timezone_str)

    await message.answer(
        f"✅ По вашему времени определён часовой пояс:\n\n"
        f"📍 {detection_result.display_name}\n\n"
        f"Подтвердите выбор:",
        reply_markup=get_timezone_confirmation_keyboard(detection_result.timezone_str),
    )
    await state.set_state(RegistrationStates.confirming_timezone)


@router.callback_query(
    RegistrationStates.confirming_timezone, F.data.startswith("tz_confirm:")
)
async def handle_timezone_confirmation(
    callback: CallbackQuery, state: FSMContext
) -> None:
    """Handle timezone confirmation."""
    await callback.answer()

    timezone_str = callback.data.split(":", 1)[1]

    # Complete registration with confirmed timezone
    await complete_registration(callback, state, timezone_str)


@router.callback_query(
    RegistrationStates.confirming_timezone, F.data == "tz:back"
)
async def handle_timezone_reselection(
    callback: CallbackQuery, state: FSMContext
) -> None:
    """Handle timezone reselection from confirmation."""
    await callback.answer()

    await callback.message.edit_text(
        "Выберите ваш часовой пояс:",
        reply_markup=get_timezone_keyboard(),
    )
    await state.set_state(RegistrationStates.waiting_for_timezone)


async def complete_registration(
    callback: CallbackQuery, state: FSMContext, timezone_str: str
) -> None:
    """Complete student registration."""
    data = await state.get_data()
    invite_code_str = data.get("invite_code_str")

    if not invite_code_str:
        await callback.message.edit_text(
            "❌ Ошибка: код приглашения не найден. Начните регистрацию заново с /start"
        )
        await state.clear()
        return

    async with get_session() as session:
        service = RegistrationService(session)

        try:
            registration_result = await service.complete_registration(
                telegram_id=callback.from_user.id,
                first_name=callback.from_user.first_name,
                last_name=callback.from_user.last_name,
                username=callback.from_user.username,
                timezone_str=timezone_str,
                invite_code_str=invite_code_str,
            )

            await callback.message.edit_text(
                f"🎉 Регистрация завершена!\n\n"
                f"Направление: {registration_result.direction.name}\n"
                f"Текущий этап: {registration_result.first_stage.name}\n"
                f"Часовой пояс: {timezone_str}\n\n"
                f"Добро пожаловать в Sputnik Offer CRM!"
            )

            logger.info(
                "Student registered",
                student_id=registration_result.student.id,
                telegram_id=callback.from_user.id,
                direction_id=registration_result.direction.id,
            )

        except InviteCodeNotFoundError:
            await callback.message.edit_text(
                "❌ Код приглашения не найден. Начните регистрацию заново с /start"
            )
        except InviteCodeAlreadyUsedError:
            await callback.message.edit_text(
                "❌ Этот код уже был использован.\n\n"
                "Обратитесь к ментору за новым кодом."
            )
        except DirectionHasNoStagesError as e:
            logger.error("Direction has no stages", error=str(e))
            await callback.message.edit_text(
                "❌ Ошибка конфигурации направления. Обратитесь к администратору."
            )
        except Exception as e:
            logger.error("Registration failed", error=str(e), exc_info=True)
            await callback.message.edit_text(
                "❌ Произошла ошибка при регистрации. Попробуйте позже или обратитесь к администратору."
            )
        finally:
            await state.clear()
