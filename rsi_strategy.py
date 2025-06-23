import asyncio
import os
import logging
from tinkoff.invest import AsyncClient, CandleInterval
from utils import TICKERS, FIGI_MAP
from order_manager import list_portfolio
from telegram_interface import request_buy_confirmation, request_sell_confirmation
from utils import quotation_to_float

# Сколько свечей использовать для RSI (обычно 14)
RSI_PERIOD = 14

# Пороговые значения
RSI_BUY = 20
RSI_SELL = 80

# Храним цены покупки для расчёта прибыли
BUY_PRICES = {}

async def fetch_candles(figi, client, interval=RSI_PERIOD + 30):
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    candles = await client.market_data.get_candles(
        figi=figi,
        from_=now - timedelta(minutes=interval * 2),
        to=now,
        interval=CandleInterval.CANDLE_INTERVAL_1_MIN
    )
    return [quotation_to_float(candle.close) for candle in candles.candles]  # close prices

def calculate_rsi(prices, period=RSI_PERIOD):
    if len(prices) < period + 1:
        return 50  # нейтральное значение, если данных мало

    gains = []
    losses = []
    for i in range(1, period + 1):
        diff = prices[-i] - prices[-i - 1]
        if diff >= 0:
            gains.append(diff)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(-diff)
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        return 100  # перекупленность
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

async def get_owned_figis():
    # Берём список купленных бумаг из портфеля
    raw = await list_portfolio()
    # Ищем FIGI из текста (или можно доработать парсер)
    figis = []
    for figi in FIGI_MAP.values():
        if figi in raw:
            figis.append(figi)
    return figis

async def run_signals():
    from tinkoff.invest.async_services import InstrumentsService, MarketDataService
    from tinkoff.invest import AsyncClient

    logging.info("Старт RSI-стратегии")

    TOKEN = os.getenv("TINKOFF_API_TOKEN")

    while True:
        try:
            async with AsyncClient(TOKEN) as client:
                for ticker in TICKERS:
                    figi = FIGI_MAP[ticker]
                    prices = await fetch_candles(figi, client)
                    if not prices:
                        continue

                    rsi = calculate_rsi(prices)
                    logging.info(f"[RSI] {ticker} ({figi}) → {rsi:.2f}")

                    # Получаем, есть ли бумага в портфеле
                    held_figis = await get_owned_figis()
                    already_bought = figi in held_figis

                    # --- Сигнал на покупку ---
                    if rsi < RSI_BUY and not already_bought:
                        last_price = prices[-1]
                        qty = 1  # Кол-во акций, можно доработать
                        await request_buy_confirmation(figi, qty, last_price)
                        BUY_PRICES[figi] = last_price  # фиксируем цену покупки

                    # --- Сигнал на продажу ---
                    if rsi > RSI_SELL and already_bought:
                        qty = 1  # Кол-во акций на продажу, доработайте по портфелю
                        buy_price = BUY_PRICES.get(figi, prices[-1])
                        curr_price = prices[-1]
                        await request_sell_confirmation(figi, qty, buy_price, curr_price)

            await asyncio.sleep(60)  # раз в минуту
        except Exception as e:
            logging.error(f"Ошибка в стратегии: {e}")
            await asyncio.sleep(30)

