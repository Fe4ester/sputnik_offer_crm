"""Keyboards for student flow."""

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def get_student_menu_keyboard() -> ReplyKeyboardMarkup:
    """Get main menu keyboard for student."""
    keyboard = [
        [KeyboardButton(text="📊 Мой прогресс")],
        [KeyboardButton(text="📅 Мои дедлайны")],
        [KeyboardButton(text="📌 Мои задачи")],
        [KeyboardButton(text="📝 Отправить")],
        [KeyboardButton(text="🌍 Сменить часовой пояс")],
        [KeyboardButton(text="❓ Помощь")],
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
    )


def get_skip_keyboard() -> ReplyKeyboardMarkup:
    """Get keyboard with skip button."""
    keyboard = [
        [KeyboardButton(text="⏭ Пропустить")],
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
    )

