"""Direction and stage management handlers for mentors."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from sputnik_offer_crm.bot.states import DirectionManagementStates
from sputnik_offer_crm.db import get_session
from sputnik_offer_crm.services import (
    DirectionCodeAlreadyExistsError,
    DirectionInUseError,
    DirectionManagementService,
    DirectionNotFoundError,
    DirectionStageInUseError,
    DirectionStageNotFoundError,
    MentorNotFoundError,
    MentorService,
)
from sputnik_offer_crm.utils.logging import get_logger

router = Router(name="direction_management")
logger = get_logger(__name__)


def get_directions_list_keyboard(directions: list) -> InlineKeyboardMarkup:
    """Build keyboard for directions list."""
    buttons = []
    for direction in directions:
        status = "✅" if direction.is_active else "❌"
        buttons.append([
            InlineKeyboardButton(
                text=f"{status} {direction.name}",
                callback_data=f"dir_view:{direction.id}",
            )
        ])
    buttons.append([
        InlineKeyboardButton(text="➕ Добавить направление", callback_data="dir_add")
    ])
    buttons.append([
        InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_menu")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_direction_actions_keyboard(direction_id: int, is_active: bool) -> InlineKeyboardMarkup:
    """Build keyboard for direction actions."""
    buttons = [
        [InlineKeyboardButton(text="📋 Этапы", callback_data=f"dir_stages:{direction_id}")],
    ]
    if is_active:
        buttons.append([
            InlineKeyboardButton(
                text="🔴 Деактивировать",
                callback_data=f"dir_deactivate:{direction_id}",
            )
        ])
    buttons.append([
        InlineKeyboardButton(text="◀️ К списку направлений", callback_data="dir_list")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_stages_list_keyboard(direction_id: int, stages: list) -> InlineKeyboardMarkup:
    """Build keyboard for stages list."""
    buttons = []
    for stage in stages:
        status = "✅" if stage.is_active else "❌"
        buttons.append([
            InlineKeyboardButton(
                text=f"{status} {stage.stage_number}. {stage.title}",
                callback_data=f"stage_view:{stage.id}",
            )
        ])
    buttons.append([
        InlineKeyboardButton(
            text="➕ Добавить этап",
            callback_data=f"stage_add:{direction_id}",
        )
    ])
    buttons.append([
        InlineKeyboardButton(
            text="◀️ К направлению",
            callback_data=f"dir_view:{direction_id}",
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_stage_actions_keyboard(stage_id: int, direction_id: int, is_active: bool) -> InlineKeyboardMarkup:
    """Build keyboard for stage actions."""
    buttons = []
    if is_active:
        buttons.append([
            InlineKeyboardButton(
                text="🔴 Деактивировать",
                callback_data=f"stage_deactivate:{stage_id}",
            )
        ])
    buttons.append([
        InlineKeyboardButton(
            text="◀️ К списку этапов",
            callback_data=f"dir_stages:{direction_id}",
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_confirmation_keyboard(action: str, entity_id: int) -> InlineKeyboardMarkup:
    """Build confirmation keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да", callback_data=f"{action}_confirm:{entity_id}"),
            InlineKeyboardButton(text="❌ Нет", callback_data=f"{action}_cancel:{entity_id}"),
        ]
    ])


@router.message(F.text == "📚 Направления и этапы")
async def show_directions_list(message: Message, state: FSMContext) -> None:
    """Show list of all directions."""
    await state.clear()

    async with get_session() as session:
        mentor_service = MentorService(session)
        try:
            await mentor_service.check_mentor_access(message.from_user.id)
        except MentorNotFoundError:
            await message.answer("❌ Доступ запрещён. Вы не являетесь ментором.")
            return

        service = DirectionManagementService(session)
        directions = await service.list_directions()

        if not directions:
            text = "📚 Направления\n\nНаправлений пока нет."
        else:
            text = "📚 Направления\n\nВыберите направление для просмотра:"

        await message.answer(text, reply_markup=get_directions_list_keyboard(directions))


@router.callback_query(F.data == "dir_list")
async def callback_show_directions_list(callback: CallbackQuery, state: FSMContext) -> None:
    """Show directions list via callback."""
    await callback.answer()
    await state.clear()

    async with get_session() as session:
        service = DirectionManagementService(session)
        directions = await service.list_directions()

        if not directions:
            text = "📚 Направления\n\nНаправлений пока нет."
        else:
            text = "📚 Направления\n\nВыберите направление для просмотра:"

        await callback.message.edit_text(
            text,
            reply_markup=get_directions_list_keyboard(directions),
        )


@router.callback_query(F.data.startswith("dir_view:"))
async def show_direction_details(callback: CallbackQuery) -> None:
    """Show direction details."""
    await callback.answer()
    direction_id = int(callback.data.split(":")[1])

    async with get_session() as session:
        service = DirectionManagementService(session)
        try:
            directions = await service.list_directions()
            direction = next((d for d in directions if d.id == direction_id), None)

            if not direction:
                await callback.message.edit_text("❌ Направление не найдено.")
                return

            status = "Активно ✅" if direction.is_active else "Неактивно ❌"
            text = (
                f"📚 Направление: {direction.name}\n\n"
                f"Код: {direction.code}\n"
                f"Статус: {status}"
            )

            await callback.message.edit_text(
                text,
                reply_markup=get_direction_actions_keyboard(direction.id, direction.is_active),
            )
        except Exception as e:
            logger.error(f"Error showing direction details: {e}")
            await callback.message.edit_text("❌ Ошибка при загрузке направления.")


@router.callback_query(F.data == "dir_add")
async def start_add_direction(callback: CallbackQuery, state: FSMContext) -> None:
    """Start adding new direction."""
    await callback.answer()
    await callback.message.edit_text(
        "➕ Добавление направления\n\n"
        "Введите код направления (латиница, без пробелов):\n"
        "Например: python, frontend, devops"
    )
    await state.set_state(DirectionManagementStates.entering_direction_code)


@router.message(DirectionManagementStates.entering_direction_code)
async def handle_direction_code_input(message: Message, state: FSMContext) -> None:
    """Handle direction code input."""
    code = message.text.strip()

    if not code or " " in code:
        await message.answer(
            "❌ Код должен быть без пробелов.\n\n"
            "Попробуйте ещё раз:"
        )
        return

    await state.update_data(direction_code=code)
    await message.answer(
        "Теперь введите название направления:\n"
        "Например: Python Backend, Frontend разработка"
    )
    await state.set_state(DirectionManagementStates.entering_direction_name)


@router.message(DirectionManagementStates.entering_direction_name)
async def handle_direction_name_input(message: Message, state: FSMContext) -> None:
    """Handle direction name input."""
    name = message.text.strip()

    if not name:
        await message.answer("❌ Название не может быть пустым.\n\nПопробуйте ещё раз:")
        return

    data = await state.get_data()
    code = data["direction_code"]

    async with get_session() as session:
        service = DirectionManagementService(session)
        try:
            direction = await service.create_direction(code=code, name=name)
            await session.commit()

            await message.answer(
                f"✅ Направление создано\n\n"
                f"Код: {direction.code}\n"
                f"Название: {direction.name}"
            )

            await state.clear()

            directions = await service.list_directions()
            await message.answer(
                "📚 Направления",
                reply_markup=get_directions_list_keyboard(directions),
            )

        except DirectionCodeAlreadyExistsError as e:
            await message.answer(f"❌ {str(e)}\n\nВведите другой код:")
            await state.set_state(DirectionManagementStates.entering_direction_code)
        except Exception as e:
            logger.error(f"Error creating direction: {e}")
            await message.answer("❌ Ошибка при создании направления.")
            await state.clear()


@router.callback_query(F.data.startswith("dir_deactivate:"))
async def confirm_deactivate_direction(callback: CallbackQuery) -> None:
    """Ask confirmation for direction deactivation."""
    await callback.answer()
    direction_id = int(callback.data.split(":")[1])

    await callback.message.edit_text(
        "⚠️ Деактивация направления\n\n"
        "Вы уверены, что хотите деактивировать это направление?\n"
        "Направление с активными студентами деактивировать нельзя.",
        reply_markup=get_confirmation_keyboard("dir_deactivate", direction_id),
    )


@router.callback_query(F.data.startswith("dir_deactivate_confirm:"))
async def handle_deactivate_direction(callback: CallbackQuery) -> None:
    """Handle direction deactivation."""
    await callback.answer()
    direction_id = int(callback.data.split(":")[1])

    async with get_session() as session:
        service = DirectionManagementService(session)
        try:
            direction = await service.deactivate_direction(direction_id)
            await session.commit()

            await callback.message.edit_text(
                f"✅ Направление '{direction.name}' деактивировано"
            )

            directions = await service.list_directions()
            await callback.message.answer(
                "📚 Направления",
                reply_markup=get_directions_list_keyboard(directions),
            )

        except DirectionNotFoundError:
            await callback.message.edit_text("❌ Направление не найдено.")
        except DirectionInUseError as e:
            await callback.message.edit_text(f"❌ {str(e)}")
        except Exception as e:
            logger.error(f"Error deactivating direction: {e}")
            await callback.message.edit_text("❌ Ошибка при деактивации направления.")


@router.callback_query(F.data.startswith("dir_deactivate_cancel:"))
async def cancel_deactivate_direction(callback: CallbackQuery) -> None:
    """Cancel direction deactivation."""
    await callback.answer()
    direction_id = int(callback.data.split(":")[1])

    async with get_session() as session:
        service = DirectionManagementService(session)
        directions = await service.list_directions()
        direction = next((d for d in directions if d.id == direction_id), None)

        if direction:
            status = "Активно ✅" if direction.is_active else "Неактивно ❌"
            text = (
                f"📚 Направление: {direction.name}\n\n"
                f"Код: {direction.code}\n"
                f"Статус: {status}"
            )
            await callback.message.edit_text(
                text,
                reply_markup=get_direction_actions_keyboard(direction.id, direction.is_active),
            )


@router.callback_query(F.data.startswith("dir_stages:"))
async def show_direction_stages(callback: CallbackQuery) -> None:
    """Show stages for direction."""
    await callback.answer()
    direction_id = int(callback.data.split(":")[1])

    async with get_session() as session:
        service = DirectionManagementService(session)
        try:
            directions = await service.list_directions()
            direction = next((d for d in directions if d.id == direction_id), None)

            if not direction:
                await callback.message.edit_text("❌ Направление не найдено.")
                return

            stages = await service.get_direction_stages(direction_id)

            if not stages:
                text = f"📋 Этапы направления '{direction.name}'\n\nЭтапов пока нет."
            else:
                text = f"📋 Этапы направления '{direction.name}'\n\nВыберите этап:"

            await callback.message.edit_text(
                text,
                reply_markup=get_stages_list_keyboard(direction_id, stages),
            )

        except DirectionNotFoundError:
            await callback.message.edit_text("❌ Направление не найдено.")
        except Exception as e:
            logger.error(f"Error showing stages: {e}")
            await callback.message.edit_text("❌ Ошибка при загрузке этапов.")


@router.callback_query(F.data.startswith("stage_view:"))
async def show_stage_details(callback: CallbackQuery) -> None:
    """Show stage details."""
    await callback.answer()
    stage_id = int(callback.data.split(":")[1])

    async with get_session() as session:
        service = DirectionManagementService(session)
        try:
            from sputnik_offer_crm.models import Stage
            from sqlalchemy import select

            result = await session.execute(select(Stage).where(Stage.id == stage_id))
            stage = result.scalar_one_or_none()

            if not stage:
                await callback.message.edit_text("❌ Этап не найден.")
                return

            status = "Активен ✅" if stage.is_active else "Неактивен ❌"
            text = (
                f"📋 Этап {stage.stage_number}: {stage.title}\n\n"
                f"Статус: {status}\n"
            )

            if stage.description:
                text += f"Описание: {stage.description}\n"

            if stage.planned_duration_days:
                text += f"Плановая длительность: {stage.planned_duration_days} дн.\n"

            await callback.message.edit_text(
                text,
                reply_markup=get_stage_actions_keyboard(
                    stage.id,
                    stage.direction_id,
                    stage.is_active,
                ),
            )

        except Exception as e:
            logger.error(f"Error showing stage details: {e}")
            await callback.message.edit_text("❌ Ошибка при загрузке этапа.")


@router.callback_query(F.data.startswith("stage_add:"))
async def start_add_stage(callback: CallbackQuery, state: FSMContext) -> None:
    """Start adding new stage."""
    await callback.answer()
    direction_id = int(callback.data.split(":")[1])

    await state.update_data(stage_direction_id=direction_id)
    await callback.message.edit_text(
        "➕ Добавление этапа\n\n"
        "Введите название этапа:"
    )
    await state.set_state(DirectionManagementStates.entering_stage_title)


@router.message(DirectionManagementStates.entering_stage_title)
async def handle_stage_title_input(message: Message, state: FSMContext) -> None:
    """Handle stage title input."""
    title = message.text.strip()

    if not title:
        await message.answer("❌ Название не может быть пустым.\n\nПопробуйте ещё раз:")
        return

    await state.update_data(stage_title=title)
    await message.answer(
        "Введите описание этапа (или отправьте '-' чтобы пропустить):"
    )
    await state.set_state(DirectionManagementStates.entering_stage_description)


@router.message(DirectionManagementStates.entering_stage_description)
async def handle_stage_description_input(message: Message, state: FSMContext) -> None:
    """Handle stage description input."""
    description = message.text.strip()

    if description == "-":
        description = None

    await state.update_data(stage_description=description)
    await message.answer(
        "Введите плановую длительность в днях (или отправьте '-' чтобы пропустить):"
    )
    await state.set_state(DirectionManagementStates.entering_stage_duration)


@router.message(DirectionManagementStates.entering_stage_duration)
async def handle_stage_duration_input(message: Message, state: FSMContext) -> None:
    """Handle stage duration input."""
    duration_text = message.text.strip()

    duration = None
    if duration_text != "-":
        try:
            duration = int(duration_text)
            if duration <= 0:
                await message.answer(
                    "❌ Длительность должна быть положительным числом.\n\n"
                    "Попробуйте ещё раз (или '-' чтобы пропустить):"
                )
                return
        except ValueError:
            await message.answer(
                "❌ Введите число или '-' чтобы пропустить.\n\n"
                "Попробуйте ещё раз:"
            )
            return

    data = await state.get_data()
    direction_id = data["stage_direction_id"]
    title = data["stage_title"]
    description = data.get("stage_description")

    async with get_session() as session:
        service = DirectionManagementService(session)
        try:
            stage = await service.create_stage(
                direction_id=direction_id,
                title=title,
                description=description,
                planned_duration_days=duration,
            )
            await session.commit()

            await message.answer(
                f"✅ Этап создан\n\n"
                f"Номер: {stage.stage_number}\n"
                f"Название: {stage.title}"
            )

            await state.clear()

            stages = await service.get_direction_stages(direction_id)
            directions = await service.list_directions()
            direction = next((d for d in directions if d.id == direction_id), None)

            if direction:
                text = f"📋 Этапы направления '{direction.name}'"
                await message.answer(
                    text,
                    reply_markup=get_stages_list_keyboard(direction_id, stages),
                )

        except DirectionNotFoundError:
            await message.answer("❌ Направление не найдено.")
            await state.clear()
        except Exception as e:
            logger.error(f"Error creating stage: {e}")
            await message.answer("❌ Ошибка при создании этапа.")
            await state.clear()


@router.callback_query(F.data.startswith("stage_deactivate:"))
async def confirm_deactivate_stage(callback: CallbackQuery) -> None:
    """Ask confirmation for stage deactivation."""
    await callback.answer()
    stage_id = int(callback.data.split(":")[1])

    await callback.message.edit_text(
        "⚠️ Деактивация этапа\n\n"
        "Вы уверены, что хотите деактивировать этот этап?\n"
        "Этап, на котором находятся активные студенты, деактивировать нельзя.",
        reply_markup=get_confirmation_keyboard("stage_deactivate", stage_id),
    )


@router.callback_query(F.data.startswith("stage_deactivate_confirm:"))
async def handle_deactivate_stage(callback: CallbackQuery) -> None:
    """Handle stage deactivation."""
    await callback.answer()
    stage_id = int(callback.data.split(":")[1])

    async with get_session() as session:
        service = DirectionManagementService(session)
        try:
            stage = await service.deactivate_stage(stage_id)
            await session.commit()

            await callback.message.edit_text(
                f"✅ Этап '{stage.title}' деактивирован"
            )

            stages = await service.get_direction_stages(stage.direction_id)
            directions = await service.list_directions()
            direction = next((d for d in directions if d.id == stage.direction_id), None)

            if direction:
                text = f"📋 Этапы направления '{direction.name}'"
                await callback.message.answer(
                    text,
                    reply_markup=get_stages_list_keyboard(stage.direction_id, stages),
                )

        except DirectionStageNotFoundError:
            await callback.message.edit_text("❌ Этап не найден.")
        except DirectionStageInUseError as e:
            await callback.message.edit_text(f"❌ {str(e)}")
        except Exception as e:
            logger.error(f"Error deactivating stage: {e}")
            await callback.message.edit_text("❌ Ошибка при деактивации этапа.")


@router.callback_query(F.data.startswith("stage_deactivate_cancel:"))
async def cancel_deactivate_stage(callback: CallbackQuery) -> None:
    """Cancel stage deactivation."""
    await callback.answer()
    stage_id = int(callback.data.split(":")[1])

    async with get_session() as session:
        try:
            from sputnik_offer_crm.models import Stage
            from sqlalchemy import select

            result = await session.execute(select(Stage).where(Stage.id == stage_id))
            stage = result.scalar_one_or_none()

            if stage:
                status = "Активен ✅" if stage.is_active else "Неактивен ❌"
                text = (
                    f"📋 Этап {stage.stage_number}: {stage.title}\n\n"
                    f"Статус: {status}\n"
                )

                if stage.description:
                    text += f"Описание: {stage.description}\n"

                if stage.planned_duration_days:
                    text += f"Плановая длительность: {stage.planned_duration_days} дн.\n"

                await callback.message.edit_text(
                    text,
                    reply_markup=get_stage_actions_keyboard(
                        stage.id,
                        stage.direction_id,
                        stage.is_active,
                    ),
                )

        except Exception as e:
            logger.error(f"Error canceling stage deactivation: {e}")
            await callback.message.edit_text("❌ Ошибка.")
