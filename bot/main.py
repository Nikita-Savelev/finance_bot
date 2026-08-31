import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
import os
from bot.components.handlers import (
    main_menu,
    sign_up,
    accounts,
    manual_entry,
    categories,
    statistics,
    import_files,
    monthly_reports,
)
from aiogram.types import BotCommand, BotCommandScopeDefault
from loguru import logger
from bot.components.finance.fx import fx_sync_loop


async def run():
    def register_handlers(dp: Dispatcher):
        main_menu.register_handlers(dp)
        sign_up.register_handlers(dp)
        accounts.register_handlers(dp)
        manual_entry.register_handlers(dp)
        categories.register_handlers(dp)
        statistics.register_handlers(dp)
        import_files.register_handlers(dp)
        monthly_reports.register_handlers(dp)

    async def set_commands(bot: Bot):
        commands = [
            BotCommand(
                command="start",
                description="Запустить бота",
            )
        ]
        await bot.set_my_commands(commands=commands, scope=BotCommandScopeDefault())

    dp = Dispatcher()
    bot_token = os.getenv("BOT_TOKEN")
    bot = Bot(bot_token)
    bot_info = await bot.get_me()
    logger.info(f'Starting bot {bot_info.username}')
    await set_commands(bot)
    admin_id = os.getenv("ADMIN_ID")
    if admin_id:
        await bot.send_message(text="/start", chat_id=admin_id)
    register_handlers(dp)
    fx_task = asyncio.create_task(fx_sync_loop(), name="fx_sync_loop")
    try:
        await dp.start_polling(bot)
    finally:
        fx_task.cancel()
        try:
            await fx_task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(run())
