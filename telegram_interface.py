import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import TELEGRAM_BOT_TOKEN, CHAT_ID

class TelegramInterface:
    def __init__(self, api):
        self.bot = Bot(token=TELEGRAM_BOT_TOKEN)
        self.dp = Dispatcher(self.bot)
        self.api = api
        self._permission_futures = {}  # {chat_id: asyncio.Future}
        self._quantity_futures = {}    # {chat_id: asyncio.Future}

        @self.dp.message_handler(commands=["start"])
        async def start(message: types.Message):
            await message.answer("Бот запущен! Доступные команды:\n/balance")

        @self.dp.message_handler(commands=["menu"])
        async def show_menu(message: types.Message):
            if str(message.chat.id) != str(CHAT_ID):
                return
            keyboard = InlineKeyboardMarkup(row_width=1)
            keyboard.add(
                InlineKeyboardButton("💰 Баланс", callback_data="menu_balance"),
                InlineKeyboardButton("📊 Прибыль за день", callback_data="menu_profit"),
                InlineKeyboardButton("📈 Транзакции за день", callback_data="menu_txn")
            )
            await message.answer("Выберите опцию:", reply_markup=keyboard)

        @self.dp.message_handler(commands=["balance"])
        async def balance(message: types.Message):
            if str(message.chat.id) != str(CHAT_ID):
                return
            try:
                balance = self.api.get_balance()
                await message.answer(f"💰 Баланс на счёте: {balance:.2f} ₽")
            except Exception as e:
                await message.answer(f"❌ Ошибка при получении баланса: {e}")

        @self.dp.callback_query_handler(lambda c: c.data in ["yes", "no"])
        async def handle_permission_callback(callback_query: types.CallbackQuery):
            if str(callback_query.message.chat.id) != str(CHAT_ID):
                return
            await self.bot.answer_callback_query(callback_query.id)

            future = self._permission_futures.get(callback_query.message.chat.id)
            if future and not future.done():
                future.set_result(callback_query.data == "yes")

        @self.dp.callback_query_handler(lambda c: c.data.startswith("qty_"))
        async def handle_quantity_callback(callback_query: types.CallbackQuery):
            if str(callback_query.message.chat.id) != str(CHAT_ID):
                return
            await self.bot.answer_callback_query(callback_query.id)

        @self.dp.callback_query_handler(lambda c: c.data.startswith("menu_"))
        async def handle_menu(callback_query: types.CallbackQuery):
            if str(callback_query.message.chat.id) != str(CHAT_ID):
                return
            data = callback_query.data
            await self.bot.answer_callback_query(callback_query.id)

            if data == "menu_balance":
                balance = self.api.get_balance()
                await self.send(f"💰 Баланс: {balance:.2f} ₽")
            elif data == "menu_profit":
                profit = self.api.get_daily_profit()
                await self.send(f"📊 Прибыль за сегодня: {profit:.2f} ₽")
            elif data == "menu_txn":
                count = self.api.get_transaction_count()
                await self.send(f"📈 Кол-во транзакций сегодня: {count}")

            qty = callback_query.data.split("_")[1]
            future = self._quantity_futures.get(callback_query.message.chat.id)
            if future and not future.done():
                future.set_result(qty)

        @self.dp.message_handler(commands=["menu_balance"])
        async def cmd_balance(message: types.Message):
            if str(message.chat.id) != str(CHAT_ID):
                return
            balance = self.api.get_balance()
            await message.answer(f"💰 Баланс: {balance:.2f} ₽")

        @self.dp.message_handler(commands=["menu_profit"])
        async def cmd_profit(message: types.Message):
            if str(message.chat.id) != str(CHAT_ID):
                return
            profit = self.api.get_daily_profit()
            await message.answer(f"📊 Прибыль за сегодня: {profit:.2f} ₽")

        @self.dp.message_handler(commands=["menu_txn"])
        async def cmd_txn(message: types.Message):
            if str(message.chat.id) != str(CHAT_ID):
                return
            count = self.api.get_today_transaction_count()
            await message.answer(f"📈 Транзакций за сегодня: {count}")
   

        @self.dp.message_handler()
        async def unknown(message: types.Message):
            if str(message.chat.id) != str(CHAT_ID):
                return
            await message.answer("❗ Неизвестная команда. Введите /start для списка доступных команд.")

    async def send(self, message: str):
        await self.bot.send_message(chat_id=CHAT_ID, text=message)

    async def ask_permission(self, message: str) -> bool:
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("✅ Да", callback_data="yes"),
            InlineKeyboardButton("❌ Нет", callback_data="no")
        )
        await self.bot.send_message(chat_id=CHAT_ID, text=message, reply_markup=keyboard)

        future = asyncio.get_event_loop().create_future()
        self._permission_futures[CHAT_ID] = future

        try:
            return await asyncio.wait_for(future, timeout=30)
        except asyncio.TimeoutError:
            await self.send("⏱ Время ожидания ответа истекло.")
            return False
        finally:
            del self._permission_futures[CHAT_ID]

    async def ask_quantity(self, message: str, options: list[str]) -> str | None:
        keyboard = InlineKeyboardMarkup(row_width=5)
        buttons = [InlineKeyboardButton(text=o, callback_data=f"qty_{o}") for o in options]
        keyboard.add(*buttons)

        await self.bot.send_message(chat_id=CHAT_ID, text=message, reply_markup=keyboard)

        future = asyncio.get_event_loop().create_future()
        self._quantity_futures[CHAT_ID] = future

        try:
            return await asyncio.wait_for(future, timeout=45)
        except asyncio.TimeoutError:
            await self.send("⏱ Время ожидания выбора количества истекло.")
            return None
        finally:
            del self._quantity_futures[CHAT_ID]

    def run(self):
        executor.start_polling(self.dp, skip_updates=True)
