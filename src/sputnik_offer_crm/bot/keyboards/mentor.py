"""Keyboards for mentor flow."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

from sputnik_offer_crm.models import Direction


def get_mentor_menu_keyboard() -> ReplyKeyboardMarkup:
    """Get main menu keyboard for mentor."""
    keyboard = [
        [KeyboardButton(text="➕ Новый код доступа")],
        [KeyboardButton(text="👤 Найти ученика")],
        [KeyboardButton(text="📝 Последние отчёты")],
        [KeyboardButton(text="📚 Направления и этапы")],
        [KeyboardButton(text="📈 Общий прогресс")],
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
    )


def get_direction_selection_keyboard(directions: list[Direction]) -> InlineKeyboardMarkup:
    """Get keyboard for direction selection."""
    buttons = []

    for direction in directions:
        buttons.append([
            InlineKeyboardButton(
                text=direction.name,
                callback_data=f"dir:{direction.id}"
            )
        ])

    # Cancel button
    buttons.append([
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_mentor_timezone_fallback_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard for mentor timezone fallback (UTC offsets only, no time input)."""
    # UTC offset options for mentor - controlled list only
    other_options = [
        ("UTC+0", "UTC"),
        ("UTC+1", "Etc/GMT-1"),
        ("UTC+2", "Etc/GMT-2"),
        ("UTC+3", "Etc/GMT-3"),
        ("UTC+4", "Etc/GMT-4"),
        ("UTC+5", "Etc/GMT-5"),
        ("UTC+6", "Etc/GMT-6"),
        ("UTC+7", "Etc/GMT-7"),
        ("UTC+8", "Etc/GMT-8"),
        ("UTC+9", "Etc/GMT-9"),
        ("UTC+10", "Etc/GMT-10"),
        ("UTC+11", "Etc/GMT-11"),
        ("UTC+12", "Etc/GMT-12"),
    ]

    buttons = []

    # UTC offset options (3 per row)
    for i in range(0, len(other_options), 3):
        row = []
        for label, tz in other_options[i:i+3]:
            row.append(
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"tz:{tz}"
                )
            )
        buttons.append(row)

    # Back button (no time input button for mentor)
    buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="tz:back")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)
