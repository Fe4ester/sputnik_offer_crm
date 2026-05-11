"""Application entry point."""

import asyncio

from sputnik_offer_crm.bot import create_bot, create_dispatcher
from sputnik_offer_crm.config import get_settings
from sputnik_offer_crm.db import init_db
from sputnik_offer_crm.utils.logging import configure_logging, get_logger


async def main() -> None:
    """Main application entry point."""
    # Load settings
    settings = get_settings()

    # Configure logging
    configure_logging(settings.log_level)
    logger = get_logger(__name__)

    logger.info("Starting Sputnik Offer CRM Bot")

    # Initialize database
    init_db()
    logger.info("Database initialized")

    # Create bot and dispatcher
    bot = create_bot()
    dp = create_dispatcher()

    logger.info("Starting polling")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
