"""Student timezone change handlers."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from sputnik_offer_crm.bot.keyboards.registration import (
    get_other_timezone_keyboard,
    get_timezone_confirmation_keyboard,
    get_timezone_keyboard,
)
from sputnik_offer_crm.bot.keyboards.student import get_student_menu_keyboard
from sputnik_offer_crm.bot.states import StudentTimezoneChangeStates
from sputnik_offer_crm.db import get_session
from sputnik_offer_crm.services import (
    StudentTimezoneService,
    TimezoneStudentNotFoundError,
)
from sputnik_offer_crm.utils.logging import get_logger
from sputnik_offer_crm.utils.timezone import detect_timezone_from_local_time

router = Router(name="student_timezone_change")
logger = get_logger(__name__)


@router.message(F.text == "🌍 Сменить часовой пояс")
async def start_timezone_change(message: Message, state: FSMContext) -> None:
    """Start timezone change flow."""
    await state.clear()

    async with get_session() as session:
        service = StudentTimezoneService(session)
        try:
            student, current_timezone = await service.get_student_timezone(
                message.from_user.id
            )

            await message.answer(
                f"🌍 Смена часового пояса\n\n"
                f"Текущий часовой пояс: {current_timezone}\n\n"
                f"Выберите новый часовой пояс:",
                reply_markup=get_timezone_keyboard(),
            )
            await state.set_state(StudentTimezoneChangeStates.selecting_timezone)

        except TimezoneStudentNotFoundError:
            await message.answer("❌ Ошибка: студент не найден.")


@router.callback_query(
    StudentTimezoneChangeStates.selecting_timezone,
    F.data.startswith("tz:"),
)
async def handle_timezone_selection(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle timezone selection."""
    await callback.answer()

    timezone_data = callback.data.split(":", 1)[1]

    if timezone_data == "other":
        await callback.message.edit_text(
            "🌍 Выберите часовой пояс из списка или введите своё время:",
            reply_markup=get_other_timezone_keyboard(),
        )
        await state.set_state(StudentTimezoneChangeStates.selecting_other_timezone)
        return

    await state.update_data(selected_timezone=timezone_data)
    await callback.message.edit_text(
        f"Вы выбрали часовой пояс: {timezone_data}\n\n"
        f"Подтвердите выбор:",
        reply_markup=get_timezone_confirmation_keyboard(timezone_data),
    )
    await state.set_state(StudentTimezoneChangeStates.confirming_timezone)


@router.callback_query(
    StudentTimezoneChangeStates.selecting_other_timezone,
    F.data.startswith("tz:"),
)
async def handle_other_timezone_selection(
    callback: CallbackQuery, state: FSMContext
) -> None:
    """Handle other timezone selection."""
    await callback.answer()

    timezone_data = callback.data.split(":", 1)[1]

    if timezone_data == "back":
        await callback.message.edit_text(
            "🌍 Выберите часовой пояс:",
            reply_markup=get_timezone_keyboard(),
        )
        await state.set_state(StudentTimezoneChangeStates.selecting_timezone)
        return

    if timezone_data == "input_time":
        await callback.message.edit_text(
            "⏰ Введите ваше текущее местное время в формате ЧЧ:ММ\n\n"
            "Например: 14:30"
        )
        await state.set_state(StudentTimezoneChangeStates.waiting_for_local_time)
        return

    await state.update_data(selected_timezone=timezone_data)
    await callback.message.edit_text(
        f"Вы выбрали часовой пояс: {timezone_data}\n\n"
        f"Подтвердите выбор:",
        reply_markup=get_timezone_confirmation_keyboard(timezone_data),
    )
    await state.set_state(StudentTimezoneChangeStates.confirming_timezone)


@router.message(StudentTimezoneChangeStates.waiting_for_local_time)
async def handle_local_time_input(message: Message, state: FSMContext) -> None:
    """Handle local time input for timezone detection."""
    local_time = message.text.strip()

    detected_timezone = detect_timezone_from_local_time(local_time)

    if not detected_timezone:
        await message.answer(
            "❌ Неверный формат времени.\n\n"
            "Пожалуйста, введите время в формате ЧЧ:ММ (например, 14:30):"
        )
        return

    await state.update_data(selected_timezone=detected_timezone)
    await message.answer(
        f"Определён часовой пояс: {detected_timezone}\n\n"
        f"Подтвердите выбор:",
        reply_markup=get_timezone_confirmation_keyboard(detected_timezone),
    )
    await state.set_state(StudentTimezoneChangeStates.confirming_timezone)


@router.callback_query(
    StudentTimezoneChangeStates.confirming_timezone,
    F.data.startswith("tz_confirm:"),
)
async def handle_timezone_confirmation(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle timezone confirmation and update."""
    await callback.answer()

    new_timezone = callback.data.split(":", 1)[1]

    async with get_session() as session:
        service = StudentTimezoneService(session)
        try:
            # Get current timezone first
            student, old_timezone = await service.get_student_timezone(
                callback.from_user.id
            )

            # Check if timezone is the same
            if old_timezone == new_timezone:
                await callback.message.edit_text(
                    f"ℹ️ Вы уже используете часовой пояс {new_timezone}.\n\n"
                    f"Часовой пояс не изменён."
                )
                await state.clear()
                await callback.message.answer(
                    "Главное меню:",
                    reply_markup=get_student_menu_keyboard(),
                )
                return

            # Update timezone
            student, old_tz, new_tz = await service.update_student_timezone(
                callback.from_user.id,
                new_timezone,
            )
            await session.commit()

            await callback.message.edit_text(
                f"✅ Часовой пояс успешно изменён\n\n"
                f"Старый: {old_tz}\n"
                f"Новый: {new_tz}\n\n"
                f"Изменение вступит в силу для всех будущих операций."
            )

            await state.clear()
            await callback.message.answer(
                "Главное меню:",
                reply_markup=get_student_menu_keyboard(),
            )

        except TimezoneStudentNotFoundError:
            await callback.message.edit_text("❌ Ошибка: студент не найден.")
            await state.clear()
        except Exception as e:
            logger.error(f"Error updating timezone: {e}")
            await callback.message.edit_text(
                "❌ Ошибка при обновлении часового пояса."
            )
            await state.clear()


@router.callback_query(
    StudentTimezoneChangeStates.confirming_timezone,
    F.data == "tz:back",
)
async def handle_timezone_reselection(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle timezone reselection."""
    await callback.answer()

    await callback.message.edit_text(
        "🌍 Выберите часовой пояс:",
        reply_markup=get_timezone_keyboard(),
    )
    await state.set_state(StudentTimezoneChangeStates.selecting_timezone)
