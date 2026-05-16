"""Student handlers."""

import structlog
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from sputnik_offer_crm.bot.keyboards.student import (
    get_skip_keyboard,
    get_student_menu_keyboard,
)
from sputnik_offer_crm.bot.states import WeeklyReportStates
from sputnik_offer_crm.db.session import get_session
from sputnik_offer_crm.services import StudentService, WeeklyReportService

logger = structlog.get_logger()

router = Router(name="student")


@router.message(F.text == "📊 Мой прогресс")
async def show_my_progress(message: Message) -> None:
    """Show student progress."""
    async with get_session() as session:
        service = StudentService(session)
        progress_info = await service.get_student_progress(message.from_user.id)

        if not progress_info:
            await message.answer(
                "📊 Прогресс не найден\n\n"
                "Вы ещё не зарегистрированы или не начали обучение.\n"
                "Обратитесь к ментору за кодом приглашения."
            )
            return

        # Check if student is active
        if not progress_info.student.is_active:
            await message.answer(
                "ℹ️ Ваш доступ к боту приостановлен.\n\n"
                "Обратитесь к ментору для получения информации."
            )
            return

        # Check if student is paused
        if progress_info.student.is_paused:
            await message.answer(
                "⏸ Вы на паузе\n\n"
                "Ваше обучение временно приостановлено.\n"
                "Обратитесь к ментору для получения информации."
            )
            return

        # Get completed stages count
        completed_count, total_count = await service.get_completed_stages_count(message.from_user.id)

        # Format started_at date
        started_date = progress_info.progress.started_at.strftime("%d.%m.%Y")

        lines = ["📊 Ваш прогресс\n"]
        lines.append(f"📚 Направление: {progress_info.direction.name}")
        lines.append(f"📍 Текущий этап: {progress_info.current_stage.title}")
        lines.append(f"📅 Дата старта: {started_date}")
        lines.append(f"🌍 Часовой пояс: {progress_info.student.timezone}")
        lines.append(f"✅ Пройдено этапов: {completed_count} из {total_count}")
        lines.append("")
        lines.append("Продолжайте в том же духе! 💪")

        await message.answer("\n".join(lines))


@router.message(F.text == "📅 Мои дедлайны")
async def show_my_deadlines(message: Message) -> None:
    """Show student deadlines and stages overview."""
    async with get_session() as session:
        service = StudentService(session)

        # Check if student is active
        progress_info = await service.get_student_progress(message.from_user.id)
        if not progress_info:
            await message.answer(
                "📅 Дедлайны не найдены\n\n"
                "Вы ещё не зарегистрированы или не начали обучение."
            )
            return

        if not progress_info.student.is_active:
            await message.answer(
                "ℹ️ Ваш доступ к боту приостановлен.\n\n"
                "Обратитесь к ментору для получения информации."
            )
            return

        # Check if student is paused
        if progress_info.student.is_paused:
            await message.answer(
                "⏸ Вы на паузе\n\n"
                "Ваше обучение временно приостановлено.\n"
                "Обратитесь к ментору для получения информации."
            )
            return

        # Get stages overview
        stages_overview = await service.get_stages_overview(message.from_user.id)

        if not stages_overview:
            await message.answer(
                "📅 Дедлайны\n\n"
                "Информация о этапах не найдена."
            )
            return

        # Format stages overview
        lines = ["📅 Этапы и дедлайны\n"]
        lines.append(f"📚 Направление: {progress_info.direction.name}\n")

        for stage_info in stages_overview:
            # Status emoji
            if stage_info.status == "completed":
                status_emoji = "✅"
                status_text = "Пройден"
            elif stage_info.status == "current":
                status_emoji = "📍"
                status_text = "Текущий"
            else:  # upcoming
                status_emoji = "⏳"
                status_text = "Предстоящий"

            lines.append(f"{status_emoji} {stage_info.stage.title}")
            lines.append(f"   Статус: {status_text}")

            # Show deadline if exists
            if stage_info.deadline:
                date_str = stage_info.deadline.strftime("%d.%m.%Y")
                if stage_info.is_overdue and stage_info.status != "completed":
                    lines.append(f"   ⚠️ Дедлайн: {date_str} (просрочен)")
                else:
                    lines.append(f"   📅 Дедлайн: {date_str}")

            lines.append("")

        await message.answer("\n".join(lines))


@router.message(F.text == "❓ Помощь")
async def show_help(message: Message) -> None:
    """Show help information."""
    help_text = (
        "❓ Помощь\n\n"
        "📊 Мой прогресс\n"
        "Показывает ваше текущее направление, этап обучения, дату старта и количество пройденных этапов.\n\n"
        "📅 Мои дедлайны\n"
        "Отображает все этапы вашего направления с их статусами (пройден, текущий, предстоящий) и дедлайнами.\n\n"
        "📌 Мои задачи\n"
        "Список задач, назначенных вам ментором. Вы можете отмечать задачи как выполненные.\n\n"
        "📝 Отправить\n"
        "Отправка еженедельного отчёта о вашей работе. Отчёт можно отправлять раз в неделю.\n\n"
        "🌍 Сменить часовой пояс\n"
        "Изменение вашего часового пояса для корректного отображения дат и времени.\n\n"
        "❗️ Если что-то не работает или нужна помощь — обратитесь к вашему ментору."
    )
    await message.answer(help_text)


@router.message(F.text == "📝 Отправить")
async def start_weekly_report(message: Message, state: FSMContext) -> None:
    """Start weekly report submission flow."""
    async with get_session() as session:
        service = WeeklyReportService(session)
        can_submit, error_message = await service.can_submit_report(message.from_user.id)

        if not can_submit:
            await message.answer(
                f"❌ {error_message}",
                reply_markup=get_student_menu_keyboard(),
            )
            return

        # Start the flow
        await state.set_state(WeeklyReportStates.waiting_for_what_did)
        await message.answer(
            "📝 Еженедельный отчёт\n\n"
            "Вопрос 1 из 3:\n\n"
            "Что вы делали на прошлой неделе? Что нового узнали? Что произошло?\n\n"
            "Напишите ваш ответ:",
            reply_markup=ReplyKeyboardRemove(),
        )


@router.message(WeeklyReportStates.waiting_for_what_did)
async def process_what_did(message: Message, state: FSMContext) -> None:
    """Process answer to 'what did you do' question."""
    if not message.text:
        await message.answer("Пожалуйста, отправьте текстовое сообщение.")
        return

    # Save answer
    await state.update_data(answer_what_did=message.text)

    # Move to next question
    await state.set_state(WeeklyReportStates.waiting_for_problems_solved)
    await message.answer(
        "Вопрос 2 из 3:\n\n"
        "С какими проблемами столкнулись и решили?\n\n"
        "Напишите ваш ответ или нажмите 'Пропустить':",
        reply_markup=get_skip_keyboard(),
    )


@router.message(WeeklyReportStates.waiting_for_problems_solved, F.text == "⏭ Пропустить")
async def skip_problems_solved(message: Message, state: FSMContext) -> None:
    """Skip 'problems solved' question."""
    await state.update_data(answer_problems_solved=None)

    # Move to next question
    await state.set_state(WeeklyReportStates.waiting_for_problems_unsolved)
    await message.answer(
        "Вопрос 3 из 3:\n\n"
        "С какими проблемами столкнулись и не можете решить? Нужна помощь?\n\n"
        "Напишите ваш ответ или нажмите 'Пропустить':",
        reply_markup=get_skip_keyboard(),
    )


@router.message(WeeklyReportStates.waiting_for_problems_solved)
async def process_problems_solved(message: Message, state: FSMContext) -> None:
    """Process answer to 'problems solved' question."""
    if not message.text:
        await message.answer("Пожалуйста, отправьте текстовое сообщение.")
        return

    # Save answer
    await state.update_data(answer_problems_solved=message.text)

    # Move to next question
    await state.set_state(WeeklyReportStates.waiting_for_problems_unsolved)
    await message.answer(
        "Вопрос 3 из 3:\n\n"
        "С какими проблемами столкнулись и не можете решить? Нужна помощь?\n\n"
        "Напишите ваш ответ или нажмите 'Пропустить':",
        reply_markup=get_skip_keyboard(),
    )


@router.message(WeeklyReportStates.waiting_for_problems_unsolved, F.text == "⏭ Пропустить")
async def skip_problems_unsolved(message: Message, state: FSMContext) -> None:
    """Skip 'problems unsolved' question and submit report."""
    await state.update_data(answer_problems_unsolved=None)
    await submit_weekly_report(message, state)


@router.message(WeeklyReportStates.waiting_for_problems_unsolved)
async def process_problems_unsolved(message: Message, state: FSMContext) -> None:
    """Process answer to 'problems unsolved' question and submit report."""
    if not message.text:
        await message.answer("Пожалуйста, отправьте текстовое сообщение.")
        return

    # Save answer
    await state.update_data(answer_problems_unsolved=message.text)
    await submit_weekly_report(message, state)


async def submit_weekly_report(message: Message, state: FSMContext) -> None:
    """Submit the weekly report."""
    data = await state.get_data()

    async with get_session() as session:
        service = WeeklyReportService(session)

        try:
            report = await service.submit_report(
                telegram_id=message.from_user.id,
                answer_what_did=data["answer_what_did"],
                answer_problems_solved=data.get("answer_problems_solved"),
                answer_problems_unsolved=data.get("answer_problems_unsolved"),
            )
            await session.commit()

            week_str = report.week_start_date.strftime("%d.%m.%Y")
            await message.answer(
                f"✅ Отчёт успешно отправлен!\n\n"
                f"Неделя: с {week_str}\n"
                f"Спасибо за ваш отчёт! 🎉",
                reply_markup=get_student_menu_keyboard(),
            )

            logger.info(
                "Weekly report submitted",
                student_id=report.student_id,
                week_start=report.week_start_date,
            )

        except ValueError as e:
            logger.error("Failed to submit weekly report", error=str(e))
            await message.answer(
                f"❌ Ошибка при отправке отчёта: {str(e)}",
                reply_markup=get_student_menu_keyboard(),
            )
        except Exception as e:
            logger.error("Unexpected error submitting weekly report", error=str(e), exc_info=True)
            await message.answer(
                "❌ Произошла ошибка при отправке отчёта. Попробуйте позже.",
                reply_markup=get_student_menu_keyboard(),
            )
        finally:
            await state.clear()


@router.message(F.text == "📌 Мои задачи")
async def handle_my_tasks(message: Message) -> None:
    """Handle student tasks view request."""
    async with get_session() as session:
        from sputnik_offer_crm.services.student_task import (
            StudentAccessDeniedError,
            StudentNotFoundError,
            StudentTaskService,
        )

        service = StudentTaskService(session)
        try:
            tasks = await service.get_student_tasks_by_telegram_id(message.from_user.id)

            if not tasks:
                await message.answer(
                    "📌 У вас пока нет задач.\n\n"
                    "Ваш ментор может назначить вам задачи для выполнения.",
                    reply_markup=get_student_menu_keyboard(),
                )
                return

            # Build tasks list with inline buttons for open tasks
            lines = ["📌 Ваши задачи\n"]
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
                    # Truncate long descriptions
                    desc = task.description
                    if len(desc) > 100:
                        desc = desc[:100] + "..."
                    lines.append(f"   📄 {desc}")

                # Add complete button for open tasks
                if task.status == "open":
                    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
                    buttons.append([
                        InlineKeyboardButton(
                            text=f"✅ Выполнить #{i}",
                            callback_data=f"complete_task:{task.id}"
                        )
                    ])

                lines.append("")

            # Create keyboard if there are buttons
            keyboard = None
            if buttons:
                from aiogram.types import InlineKeyboardMarkup
                keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

            await message.answer(
                "\n".join(lines),
                reply_markup=keyboard,
            )

            logger.info(
                "Student viewed tasks",
                student_id=message.from_user.id,
                tasks_count=len(tasks),
            )

        except StudentNotFoundError:
            await message.answer(
                "❌ Ваш профиль не найден.",
                reply_markup=get_student_menu_keyboard(),
            )
        except StudentAccessDeniedError as e:
            await message.answer(
                f"ℹ️ {str(e)}",
                reply_markup=get_student_menu_keyboard(),
            )
        except Exception as e:
            logger.error("Failed to get student tasks", error=str(e), exc_info=True)
            await message.answer(
                "❌ Не удалось загрузить задачи. Попробуйте позже.",
                reply_markup=get_student_menu_keyboard(),
            )


@router.callback_query(F.data.startswith("complete_task:"))
async def handle_complete_task(callback: CallbackQuery) -> None:
    """Handle task completion by student."""
    await callback.answer()

    task_id = int(callback.data.split(":", 1)[1])

    async with get_session() as session:
        from sputnik_offer_crm.services.student_task import (
            StudentTaskService,
            TaskNotFoundError,
            TaskAlreadyCompletedError,
            InvalidTaskTransitionError,
        )

        service = StudentTaskService(session)
        try:
            task = await service.complete_task(task_id, callback.from_user.id)

            await callback.message.edit_text(
                f"✅ Задача выполнена!\n\n"
                f"📝 {task.title}\n"
                f"🎉 Отличная работа!"
            )

            logger.info(
                "Student completed task",
                student_id=callback.from_user.id,
                task_id=task_id,
            )

        except TaskNotFoundError:
            await callback.message.edit_text("❌ Задача не найдена.")
        except TaskAlreadyCompletedError:
            await callback.message.edit_text("ℹ️ Эта задача уже выполнена.")
        except InvalidTaskTransitionError:
            await callback.message.edit_text("❌ Невозможно выполнить эту задачу.")
        except Exception as e:
            logger.error("Failed to complete task", error=str(e), exc_info=True)
            await callback.message.edit_text("❌ Не удалось выполнить задачу.")
