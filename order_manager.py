import os
from tinkoff.invest import AsyncClient, OrderDirection, OrderType
from tinkoff.invest.schemas import AccountType
from tinkoff.invest.exceptions import InvestError

TOKEN = os.getenv("TINKOFF_API_TOKEN")
ACCOUNT_ID = os.getenv("TINKOFF_ACCOUNT_ID")

class NotEnoughMoney(Exception):
    pass

async def list_accounts():
    async with AsyncClient(TOKEN) as client:
        accounts = await client.users.get_accounts()
        return '\n'.join([f"{a.id}: {a.type}" for a in accounts.accounts])

async def list_portfolio():
    from tinkoff.invest import AsyncClient
    import os

    TOKEN = os.getenv("TINKOFF_API_TOKEN")
    ACCOUNT_ID = os.getenv("TINKOFF_ACCOUNT_ID")
    async with AsyncClient(TOKEN) as client:
        portfolio = await client.operations.get_portfolio(account_id=ACCOUNT_ID)
        positions = portfolio.positions
        result = []
        for p in positions:
            qty = float(p.quantity.units) + p.quantity.nano / 1e9
            # Получаем тикер и название инструмента по FIGI
            try:
                ins = await client.instruments.find_instrument(query=p.figi)
                if ins.instruments:
                    ticker = ins.instruments[0].ticker
                    name = ins.instruments[0].name
                else:
                    ticker = "—"
                    name = "—"
            except Exception:
                ticker = "—"
                name = "—"
            result.append(f"{name} ({ticker}, {p.figi}): {qty} шт.")
        return '\n'.join(result) if result else "Портфель пуст"

async def buy_figi(figi, qty, price):
    async with AsyncClient(TOKEN) as client:
        portfolio = await client.operations.get_portfolio(account_id=ACCOUNT_ID)
        rub = next((a for a in portfolio.positions if a.figi == 'RUB000UTSTOM'), None)
        balance = float(rub.quantity.units) + rub.quantity.nano / 1e9 if rub else 0
        cost = qty * price
        if cost > balance:
            raise NotEnoughMoney()
        await client.orders.post_order(
            account_id=ACCOUNT_ID,
            figi=figi,
            quantity=qty,
            direction=OrderDirection.ORDER_DIRECTION_BUY,
            order_type=OrderType.ORDER_TYPE_MARKET,
        )
        return True

async def sell_figi(figi, qty, price):
    async with AsyncClient(TOKEN) as client:
        await client.orders.post_order(
            account_id=ACCOUNT_ID,
            figi=figi,
            quantity=qty,
            direction=OrderDirection.ORDER_DIRECTION_SELL,
            order_type=OrderType.ORDER_TYPE_MARKET,
        )
        return True

async def get_last_price(figi):
    async with AsyncClient(TOKEN) as client:
        r = await client.market_data.get_last_prices(figis=[figi])
        if r.last_prices and len(r.last_prices) > 0:
            lp = r.last_prices[0]
            price = float(lp.price.units) + lp.price.nano / 1e9
            return price
        return None

async def get_average_buy_price(figi):
    async with AsyncClient(TOKEN) as client:
        pf = await client.operations.get_portfolio(account_id=ACCOUNT_ID)
        for p in pf.positions:
            if p.figi == figi:
                avg_price = float(p.average_position_price.units) + p.average_position_price.nano / 1e9
                return avg_price
        return None
