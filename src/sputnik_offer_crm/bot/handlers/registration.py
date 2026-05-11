"""Registration handlers."""

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from sputnik_offer_crm.bot.keyboards import (
    get_other_timezone_keyboard,
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
    """Handle /start command with optional invite code."""
    # Check if student already registered
    async with get_session() as session:
        service = RegistrationService(session)
        existing_student = await service.check_student_exists(message.from_user.id)

        if existing_student:
            await show_student_menu(message)
            await state.clear()
            return

    # Check for invite code in command args
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
            "🌍 Выберите ваш часовой пояс:",
            reply_markup=get_other_timezone_keyboard(),
        )
        return

    if timezone_data == "back":
        await callback.message.edit_text(
            "Выберите ваш часовой пояс:",
            reply_markup=get_timezone_keyboard(),
        )
        return

    # Complete registration
    await complete_registration(callback, state, timezone_data)


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
