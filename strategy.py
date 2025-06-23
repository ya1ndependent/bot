import logging
from tinkoff_api import TinkoffAPI
from config import FIGI

class TradingStrategy:
    def __init__(self, bot):
        self.api = TinkoffAPI()
        self.bot = bot
        self.position = self.load_position()
        self.last_buy_price = self.load_last_buy_price()

    def save_position(self, state: bool):
        with open("position.txt", "w") as f:
            f.write("1" if state else "0")

    def load_position(self) -> bool:
        try:
            with open("position.txt", "r") as f:
                return f.read().strip() == "1"
        except FileNotFoundError:
            return False

    def save_last_buy_price(self, price: float):
        with open("buy_price.txt", "w") as f:
            f.write(str(price))

    def load_last_buy_price(self) -> float:
        try:
            with open("buy_price.txt", "r") as f:
                return float(f.read().strip())
        except FileNotFoundError:
            return 0.0

    async def run(self):
        logging.info(f"[DEBUG] self.position = {self.position}")

        quantity = self.api.get_quantity(FIGI)
        if quantity > 0 and not self.position:
            self.position = True
            self.save_position(True)
            logging.info(f"📌 Обнаружены акции {FIGI} в портфеле. Устанавливаю позицию = True")

        try:
            if not self.api.is_market_open():
                logging.info("📉 Рынок закрыт. Торговля приостановлена.")
                return

            rsi = self.api.get_rsi(FIGI)
            logging.info(f"[RSI] Значение RSI для {FIGI}: {rsi}")
            await self.bot.send(f"[RSI] Текущее значение RSI: {rsi}")

            # ======= УСЛОВИЕ НА ПОКУПКУ =======
            if rsi < 45 and not self.position:
                logging.info("🔔 Условие на покупку выполнено.")
                if await self.bot.ask_permission("RSI < 45. Купить?"):
                    balance = self.api.get_balance()
                    await self.bot.send(f"💰 Баланс на счёте: {balance:.2f} ₽")
                    try:
                        price, max_qty = self.api.get_lot_price_and_max_quantity(FIGI, balance)
                        if max_qty == 0:
                            await self.bot.send("❌ Недостаточно средств даже на один лот.")
                            return
                        options = [str(i) for i in range(1, max_qty + 1)]
                        qty_str = await self.bot.ask_quantity("Сколько акций купить?", options)
                        if not qty_str:
                            await self.bot.send("❌ Покупка отменена.")
                            return
                        qty = int(qty_str)
                        price = self.api.buy(FIGI, qty)
                        if price:
                            self.save_last_buy_price(price)
                        self.save_position(True)
                        self.position = True
                        logging.info("Сделка выполнена: ПОКУПКА")
                        await self.bot.send(f"✅ Куплено {qty} акций по цене {price:.2f} ₽")
                    except Exception as e:
                        logging.exception("Ошибка при покупке:")
                        await self.bot.send(f"❌ Ошибка при покупке: {e}")

            # ======= УСЛОВИЕ НА ПРОДАЖУ =======
            if rsi > 60 and self.position:
                logging.info("🔔 Условие на продажу выполнено.")
                try:
                    quantity = self.api.get_quantity(FIGI)
                    if quantity == 0:
                        await self.bot.send("⚠️ Нет акций для продажи.")
                        self.save_position(False)
                        return

                    current_price = self.api.get_last_price(FIGI)
                    profit_per_share = current_price - self.last_buy_price
                    total_profit = profit_per_share * quantity

                    msg = (
                        f"RSI > 60. Продать?\n"
                        f"Купили: {self.last_buy_price:.2f} ₽\n"
                        f"Продадим: {current_price:.2f} ₽\n"
                        f"📈 Прибыль: {total_profit:.2f} ₽"
                    )

                    if await self.bot.ask_permission(msg):
                        self.api.sell(FIGI, quantity)
                        self.save_position(False)
                        self.position = False
                        logging.info("Сделка выполнена: ПРОДАЖА")
                        await self.bot.send(
                            f"✅ Продано {quantity} акций по цене {current_price:.2f} ₽\n"
                            f"📈 Прибыль: {total_profit:.2f} ₽"
                        )
        except Exception as e:
            logging.exception("Ошибка при продаже:")
            await self.bot.send(f"❌ Ошибка при продаже: {e}")
