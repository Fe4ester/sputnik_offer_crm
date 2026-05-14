"""Mentor analytics and export handlers."""

from aiogram import F, Router
from aiogram.types import BufferedInputFile, Message

from sputnik_offer_crm.db import get_session
from sputnik_offer_crm.services import (
    MentorAnalyticsService,
    MentorNotFoundError,
    MentorService,
)
from sputnik_offer_crm.utils.logging import get_logger

router = Router(name="mentor_analytics")
logger = get_logger(__name__)


@router.message(F.text == "📈 Общий прогресс")
async def show_overall_progress(message: Message) -> None:
    """Show overall progress and export data."""
    async with get_session() as session:
        mentor_service = MentorService(session)
        try:
            await mentor_service.check_mentor_access(message.from_user.id)
        except MentorNotFoundError:
            await message.answer("❌ Доступ запрещён. Вы не являетесь ментором.")
            return

        analytics_service = MentorAnalyticsService(session)

        try:
            # Get summary data
            directions = await analytics_service.get_direction_summaries()
            stages = await analytics_service.get_stage_progress()
            deadlines = await analytics_service.get_all_deadlines()

            # Check if there's any data
            if not directions and not stages and not deadlines:
                await message.answer(
                    "📈 Общий прогресс\n\n"
                    "Данных пока нет. Добавьте направления и учеников для начала работы."
                )
                return

            # Build summary text
            summary_text = "📈 Общий прогресс\n\n"

            if directions:
                summary_text += "📊 Сводка по направлениям:\n"
                for d in directions:
                    summary_text += (
                        f"\n{d.direction_name}:\n"
                        f"  • Всего: {d.total_students}\n"
                        f"  • Активных: {d.active_students}\n"
                        f"  • На паузе: {d.paused_students}\n"
                        f"  • Отчислено: {d.dropped_students}\n"
                        f"  • С оффером: {d.completed_with_offer}\n"
                    )

            # Count overdue deadlines
            overdue_count = sum(1 for d in deadlines if d.is_overdue)
            if deadlines:
                summary_text += f"\n\n⏰ Дедлайны:\n"
                summary_text += f"  • Всего: {len(deadlines)}\n"
                summary_text += f"  • Просрочено: {overdue_count}\n"

            summary_text += "\n\n📎 Экспортирую детальные данные в CSV..."

            await message.answer(summary_text)

            # Export to CSV
            directions_csv, stages_csv, deadlines_csv = (
                await analytics_service.export_to_csv()
            )

            # Send CSV files
            await message.answer_document(
                BufferedInputFile(
                    directions_csv.encode("utf-8-sig"),
                    filename="directions_summary.csv",
                ),
                caption="📊 Сводка по направлениям",
            )

            await message.answer_document(
                BufferedInputFile(
                    stages_csv.encode("utf-8-sig"),
                    filename="stages_progress.csv",
                ),
                caption="📋 Прогресс по этапам",
            )

            if deadlines:
                await message.answer_document(
                    BufferedInputFile(
                        deadlines_csv.encode("utf-8-sig"),
                        filename="deadlines.csv",
                    ),
                    caption="⏰ Дедлайны",
                )

            await message.answer(
                "✅ Экспорт завершён\n\n"
                "Файлы можно открыть в Excel, Google Sheets или любом другом редакторе таблиц."
            )

        except Exception as e:
            logger.error(f"Error generating analytics: {e}")
            await message.answer(
                "❌ Ошибка при формировании отчёта. Попробуйте позже."
            )
