"""Keyboards for registration flow."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Timezone mapping based on ТЗ requirements
TIMEZONE_OPTIONS = [
    ("Москва", "Europe/Moscow"),
    ("Калининград", "Europe/Kaliningrad"),
    ("Самара", "Europe/Samara"),
    ("Екатеринбург", "Asia/Yekaterinburg"),
    ("Омск", "Asia/Omsk"),
    ("Красноярск", "Asia/Krasnoyarsk"),
    ("Новосибирск", "Asia/Novosibirsk"),
    ("Иркутск", "Asia/Irkutsk"),
    ("Владивосток", "Asia/Vladivostok"),
    ("Ереван", "Asia/Yerevan"),
    ("Тбилиси", "Asia/Tbilisi"),
    ("Дубай", "Asia/Dubai"),
    ("Алматы", "Asia/Almaty"),
    ("Бишкек", "Asia/Bishkek"),
]


def get_timezone_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard with timezone options."""
    buttons = []

    # Timezone options (2 per row)
    for i in range(0, len(TIMEZONE_OPTIONS), 2):
        row = []
        for city, tz in TIMEZONE_OPTIONS[i:i+2]:
            row.append(
                InlineKeyboardButton(
                    text=city,
                    callback_data=f"tz:{tz}"
                )
            )
        buttons.append(row)

    # "Other" button
    buttons.append([
        InlineKeyboardButton(text="🌍 Другой", callback_data="tz:other")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_other_timezone_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard for manual timezone input fallback."""
    # Fallback options for "Other" - common UTC offsets
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

    # Back button
    buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="tz:back")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)
