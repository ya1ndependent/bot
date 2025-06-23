import datetime
import numpy as np
import uuid
import pytz
from tinkoff.invest import Client, CandleInterval, OrderDirection, OrderType
from config import TINKOFF_API_TOKEN, TINKOFF_ACCOUNT_ID

class TinkoffAPI:
    def __init__(self):
        self.token = TINKOFF_API_TOKEN

    def is_market_open(self):
        now = datetime.datetime.now(pytz.timezone("Europe/Moscow"))
        # Пн–Пт с 10:00 до 18:45
        return now.weekday() < 5 and (
            datetime.time(10, 0) <= now.time() <= datetime.time(18, 45)
        )

    
    def get_portfolio(self):
        with Client(self.token) as client:
            return client.operations.get_portfolio(account_id=TINKOFF_ACCOUNT_ID).positions

    def get_position_by_figi(self, figi):
        positions = self.get_portfolio()
        for pos in positions:
            if pos.figi == figi:
                return pos
        return None

    def get_last_price(self, figi):
        with Client(self.token) as client:
            resp = client.market_data.get_last_prices(figi=[figi])
            if resp.last_prices:
                return float(resp.last_prices[0].price.units) + float(resp.last_prices[0].price.nano) / 1e9
            return None

    def get_lot_price_and_max_quantity(self, figi, balance):
        price = self.get_last_price(figi)
        if price:
            quantity = int(balance // price)
            return price, quantity
        return None, 0


    def get_rsi(self, figi, interval=CandleInterval.CANDLE_INTERVAL_5_MIN, window=14):
        now = datetime.datetime.utcnow()
        from_time = now - datetime.timedelta(minutes=interval.value * (window + 50))

        with Client(self.token) as client:
            candles = client.market_data.get_candles(
                figi=figi,
                from_=from_time,
                to=now,
                interval=interval
            ).candles

        if len(candles) < window + 1:
            return 50  # fallback

        closes = np.array([c.close.units + c.close.nano / 1e9 for c in candles])

        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.mean(gains[-window:])
        avg_loss = np.mean(losses[-window:])

        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return round(rsi, 2)

    def get_balance(self) -> float:
        with Client(self.token) as client:
            accounts = client.users.get_accounts()
            account_id = accounts.accounts[0].id

            limits = client.operations.get_withdraw_limits(account_id=account_id)
            money = limits.money
            for item in money:
                if item.currency == "rub":
                    return float(item.units) + float(item.nano) / 1e9

            return 0.0
    
    def buy(self, figi, quantity=1):
        from tinkoff.invest import Client, OrderDirection, OrderType

        try:
            order_id = str(uuid.uuid4())
            with Client(self.token) as client:
                response = client.orders.post_order(
                    order_id=order_id,
                    figi=figi,
                    quantity=quantity,
                    account_id=TINKOFF_ACCOUNT_ID,
                    order_type=OrderType.ORDER_TYPE_MARKET,
                    direction=OrderDirection.ORDER_DIRECTION_BUY
                )
                # Получаем цену сделки
                order_state = client.orders.get_order_state(account_id=TINKOFF_ACCOUNT_ID, order_id=order_id)
                if order_state and order_state.average_position_price:
                    price = float(order_state.average_position_price.units) + float(order_state.average_position_price.nano) / 1e9
                    # Сохраняем цену покупки
                    with open("buy_price.txt", "w") as f:
                        f.write(str(price))
                    print(f"✅ Куплено по цене: {price}")
                    return price
                else:
                    print("⚠️ Не удалось получить цену покупки.")
                    return None
        except Exception as e:
            print(f"❌ Ошибка при покупке: {e}")
            return None

    def sell(self, figi, quantity=1):
        from tinkoff.invest import Client, OrderDirection, OrderType

        try:
            with Client(self.token) as client:
                response = client.orders.post_order(
                    order_id=str(uuid.uuid4()),
                    figi=figi,
                    quantity=quantity,
                    account_id=TINKOFF_ACCOUNT_ID,
                    order_type=OrderType.ORDER_TYPE_MARKET,
                    direction=OrderDirection.ORDER_DIRECTION_SELL
                )
                print(f"✅ Успешная продажа: {response}")
                return response
        except Exception as e:
            print(f"❌ Ошибка при продаже: {e}")
            return None

    def get_quantity(self, figi):
        position = self.get_position_by_figi(figi)
        if position:
            return int(position.quantity.units + position.quantity.nano / 1e9)
        return 0
    def get_daily_profit(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        with Client(self.token) as client:
            operations_response = client.operations.get_operations(
                account_id=TINKOFF_ACCOUNT_ID,
                from_=today_start,
                to=now
            )
            operations = operations_response.operations

        profit = 0.0
        for op in operations:
            if op.payment:
                sign = -1 if op.operation_type.name.lower().startswith("buy") else 1
                value = (op.payment.units + op.payment.nano / 1e9) * sign
                profit += value

        return round(profit, 2)

    def get_today_transaction_count(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        with Client(self.token) as client:
            operations_response = client.operations.get_operations(
                account_id=TINKOFF_ACCOUNT_ID,
                from_=today_start,
                to=now
            )

        return len(operations_response.operations)
