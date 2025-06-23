import asyncio
import logging
from config import FIGI
from strategy import TradingStrategy
from telegram_interface import TelegramInterface
from tinkoff_api import TinkoffAPI

logging.basicConfig(
    filename="logs/bot.log",
    level=logging.INFO,
    format="%(asctime)s:%(levelname)s:%(message)s"
)

async def main():
    api = TinkoffAPI()
    bot = TelegramInterface(api)
    strategy = TradingStrategy(bot)

    # Запускаем Telegram-бота (обработка команд)
    asyncio.create_task(bot.dp.start_polling())

    # Запускаем торговую стратегию раз в 5 минут
    while True:
        try:
            await strategy.run()
        except Exception as e:
            logging.exception("Ошибка в основном цикле: %s", e)
        await asyncio.sleep(300)  # 5 минут = 300 секунд

if __name__ == "__main__":
    asyncio.run(main())
