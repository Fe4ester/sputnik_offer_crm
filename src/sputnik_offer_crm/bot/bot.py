"""Bot initialization."""

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from sputnik_offer_crm.bot.handlers import router
from sputnik_offer_crm.config import get_settings


def create_bot() -> Bot:
    """Create and configure bot instance."""
    settings = get_settings()
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher() -> Dispatcher:
    """Create and configure dispatcher with handlers."""
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.include_router(router)
    return dp
