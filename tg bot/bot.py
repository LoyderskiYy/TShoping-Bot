import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError

import uvicorn
from web_admin import app as web_app, set_bot_instance
from config import BOT_TOKEN, ADMIN_IDS, PROXY_URL, WEB_ADMIN_HOST, WEB_ADMIN_PORT, WEB_ADMIN_PASSWORD
from database.db import init_db
from handlers import (
    start_router,
    profile_router,
    catalog_router,
    orders_router,
    support_router,
    admin_router,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info("Инициализация базы данных...")
    await init_db()
    logger.info("База данных готова к работе.")

    if not BOT_TOKEN or "ABCdefGhIJKlmNoPQRsTUVwxyZ" in BOT_TOKEN:
        logger.error(
            "\n"
            "===========================================================\n"
            "ОШИБКА: Токен Telegram-бота не указан!\n"
            "Пожалуйста, укажите действительный BOT_TOKEN в файле .env\n"
            "===========================================================\n"
        )
        return

    logger.info(f"Запуск бота... Найдено администраторов: {len(ADMIN_IDS)}")

    session: AiohttpSession | None = None
    if PROXY_URL:
        logger.info(f"Используется прокси для Telegram API: {PROXY_URL}")
        session = AiohttpSession(proxy=PROXY_URL)

    bot = Bot(
        token=BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    set_bot_instance(bot)

    # Регистрация роутеров
    dp.include_router(start_router)
    dp.include_router(profile_router)
    dp.include_router(catalog_router)
    dp.include_router(orders_router)
    dp.include_router(support_router)
    dp.include_router(admin_router)

    # Запуск сервера веб-админки
    web_config = uvicorn.Config(
        web_app,
        host=WEB_ADMIN_HOST,
        port=WEB_ADMIN_PORT,
        log_level="warning",
    )
    web_server = uvicorn.Server(web_config)

    logger.info(
        f"\n"
        f"===========================================================\n"
        f"🌐 ВЕБ-АДМИНКА ЗАПУЩЕНА:\n"
        f"Ссылка: http://localhost:{WEB_ADMIN_PORT}\n"
        f"Пароль для входа: {WEB_ADMIN_PASSWORD}\n"
        f"===========================================================\n"
    )

    async def run_bot_polling():
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(bot)
        except TelegramNetworkError as net_err:
            logger.error(
                "\n"
                "===========================================================\n"
                "ОШИБКА ПОДКЛЮЧЕНИЯ К TELEGRAM API:\n"
                f"{net_err}\n\n"
                "Сайт api.telegram.org недоступен с вашего интернет-провайдера.\n"
                "РЕШЕНИЕ:\n"
                "1. Включите любой VPN на вашем компьютере (Outline, Amnezia, VLESS и др.)\n"
                "ИЛИ\n"
                "2. Укажите локальный или внешний прокси в файле .env:\n"
                "   PROXY_URL=socks5://127.0.0.1:10808 (или http://ip:port)\n"
                "===========================================================\n"
            )

    await asyncio.gather(
        web_server.serve(),
        run_bot_polling(),
    )




if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")
