"""Telegram signal publisher.

This file lives at bot/telegram/publisher.py. The ``bot.telegram`` package is
distinct from the top-level ``telegram`` pip package, so there is no import
shadowing — ``from telegram import Bot`` correctly resolves to python-telegram-bot.

python-telegram-bot v21 is fully async. A fresh Bot is created and closed inside
each async send via the async context manager, making it safe to call from
separate asyncio.run() invocations (one per scheduler tick).
"""

from __future__ import annotations

import datetime
from typing import Any

from loguru import logger
from telegram import Bot
from telegram.error import TelegramError

from bot.config.settings import settings

_DIRECTION_EMOJI = {"BUY": "🟢 LONG", "SELL": "🔴 SHORT"}
_WAT = datetime.timezone(datetime.timedelta(hours=1))  # West Africa Time = UTC+1


def format_signal_message(signal: dict[str, Any]) -> str:
    """Build a human-readable Telegram signal alert string.

    Args:
        signal: Dict with keys: direction, entry_price, stop_loss, take_profit,
                risk_reward, confidence, symbol, timeframe, timestamp.

    Returns:
        Formatted multi-line string.
    """
    direction = signal["direction"]
    entry = float(signal["entry_price"])
    sl = float(signal["stop_loss"])
    tp = float(signal["take_profit"])
    rr = float(signal.get("risk_reward", 0))
    confidence = float(signal["confidence"])
    symbol = signal.get("symbol", settings.SYMBOL)
    timeframe = signal.get("timeframe", settings.TIMEFRAME)

    # Timestamp: Unix ms → WAT datetime string
    ts_ms = signal.get("timestamp")
    if ts_ms:
        dt_wat = datetime.datetime.fromtimestamp(int(ts_ms) / 1000, tz=_WAT)
        time_str = dt_wat.strftime("%Y-%m-%d %H:%M WAT")
    else:
        time_str = datetime.datetime.now(_WAT).strftime("%Y-%m-%d %H:%M WAT")

    sl_pct = (sl - entry) / entry * 100
    tp_pct = (tp - entry) / entry * 100

    header = "[TESTNET] 🤖 SIGNAL ALERT" if settings.BINANCE_TESTNET else "🤖 SIGNAL ALERT"
    dir_label = _DIRECTION_EMOJI.get(direction, direction)
    sep = "─" * 33

    return (
        f"{sep}\n"
        f"{header}\n\n"
        f"Pair:          {symbol}\n"
        f"Direction:     {dir_label}\n"
        f"Entry:         ${entry:,.2f}\n"
        f"Stop loss:     ${sl:,.2f}  ({sl_pct:+.1f}%)\n"
        f"Take profit:   ${tp:,.2f}  ({tp_pct:+.1f}%)\n"
        f"Risk/Reward:   1 : {rr:.1f}\n"
        f"Confidence:    {confidence:.0%}\n"
        f"Timeframe:     {timeframe}\n"
        f"Time:          {time_str}\n\n"
        f"⚠️ Manage your risk. Not financial advice.\n"
        f"{sep}"
    )


async def publish_signal(signal: dict[str, Any]) -> bool:
    """Format and publish a trading signal to the Telegram channel.

    Args:
        signal: Signal dict (see format_signal_message for expected keys).

    Returns:
        True if delivered, False on any error (never raises).
    """
    message = format_signal_message(signal)
    logger.debug("Publishing signal:\n{}", message)
    return await _send(message)


async def send_alert(message: str) -> bool:
    """Send a plain-text alert to the Telegram channel.

    Used for errors, daily summaries, circuit breaker notifications, startup ping.

    Args:
        message: Alert body.

    Returns:
        True if delivered, False on any error (never raises).
    """
    return await _send(message)


async def _send(text: str) -> bool:
    """Send *text* to settings.TELEGRAM_CHANNEL_ID using a fresh Bot instance.

    Args:
        text: Message body.

    Returns:
        True on success, False on TelegramError or any exception.
    """
    try:
        async with Bot(token=settings.TELEGRAM_BOT_TOKEN) as bot:
            await bot.send_message(
                chat_id=settings.TELEGRAM_CHANNEL_ID,
                text=text,
                parse_mode=None,
            )
        logger.info("Telegram sent ({} chars)", len(text))
        return True
    except TelegramError as exc:
        logger.error("Telegram send failed: {}", exc)
        return False
    except Exception as exc:
        logger.error("Unexpected Telegram error: {}", exc)
        return False
