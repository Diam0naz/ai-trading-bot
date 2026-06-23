"""Main bot orchestration loop — with live order execution.

Run with:
    python -m bot.loop

Every 15 minutes:
  - If a position is open:
      1. Run model — if SELL signal fires, close early
      2. Otherwise check SL/TP against live price
  - If no position:
      1. Run model — if BUY fires above threshold, execute entry
      2. SELL on spot with no position = publish only (no shorting)

Daily at 07:00 UTC (08:00 WAT):
  - Send performance summary using real closed-trade PnL
"""

from __future__ import annotations

import asyncio
import datetime
import pandas as pd
import signal
import sys
import time
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from bot.config.settings import settings
from bot.data.fetcher import fetch_ohlcv
from bot.data.storage import (
    close_trade_record,
    get_candles,
    get_daily_signals,
    get_open_trade,
    get_trades,
    mark_signal_published,
    save_signal,
    save_trade,
    upsert_candles,
    upsert_daily_stats,
)
from bot.model.predictor import predict_signal
from bot.risk.manager import calculate_levels, evaluate_outcomes, position_size
from bot.telegram.publisher import publish_signal, send_alert

# Binance minimum order notional (USDT) — orders below this are rejected
_MIN_NOTIONAL_USDT = 10.0


# ─────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────


def _setup_logging() -> None:
    logger.remove()
    logger.add(
        sys.stdout,
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level:<8}</level> | {message}",
        colorize=True,
    )
    logger.add(
        settings.LOG_PATH,
        rotation="10 MB",
        retention="30 days",
        level="DEBUG",
        compression="gz",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    )


# ─────────────────────────────────────────────
# Startup checks
# ─────────────────────────────────────────────


def _check_prerequisites() -> None:
    if not Path(settings.DATABASE_PATH).exists():
        sys.exit(
            f"DB not found at {settings.DATABASE_PATH}.\n"
            f"Run: sqlite3 db/trading_bot.db < db/init_db.sql"
        )
    if not Path(settings.MODEL_PATH).exists():
        sys.exit(
            f"Model not found at {settings.MODEL_PATH}.\n"
            f"Run: python -m bot.model.trainer"
        )


# ─────────────────────────────────────────────
# Circuit breaker — uses real closed-trade PnL
# ─────────────────────────────────────────────


def _circuit_breaker_active() -> bool:
    """Return True if today's realized PnL has breached the max daily loss.

    Queries actual closed trades for today. Falls back to False if no trades
    have closed or if the balance fetch fails.
    """
    from bot.data.storage import get_today_realized_pnl
    from bot.execution.trader import get_free_balance

    realized_usdt = get_today_realized_pnl()
    if realized_usdt is None:
        return False

    try:
        balance = get_free_balance("USDT")
        if balance <= 0:
            return False
        loss_pct = realized_usdt / balance
        if loss_pct < -settings.MAX_DAILY_LOSS_PCT:
            logger.warning(
                "Circuit breaker: realized PnL {:.2f} USDT ({:.2%}) breaches -{:.0%} limit",
                realized_usdt, loss_pct, settings.MAX_DAILY_LOSS_PCT,
            )
            return True
    except Exception as exc:
        logger.warning("Circuit breaker balance check failed: {} — skipping", exc)

    return False


# ─────────────────────────────────────────────
# Position closing helpers
# ─────────────────────────────────────────────


def _close_trade(trade: dict, reason: str) -> None:
    """Close an open position at market and record the outcome.

    Args:
        trade:  Open trade row from the DB.
        reason: 'stop_loss' | 'take_profit' | 'signal' | 'manual'
    """
    from bot.execution.trader import close_position, get_current_price

    entry     = float(trade["entry_price"])
    qty       = float(trade["quantity"])
    notional  = float(trade["notional"])
    direction = trade["direction"]

    try:
        fill       = close_position(trade["symbol"], qty)
        exit_price = fill["avg_price"] or get_current_price(trade["symbol"])
        pnl_pct    = (exit_price - entry) / entry          # positive = win for BUY
        pnl_usdt   = pnl_pct * notional

        close_trade_record(trade["id"], {
            "exit_order_id": fill["order_id"],
            "exit_price":    exit_price,
            "exit_reason":   reason,
            "pnl_usdt":      pnl_usdt,
            "pnl_pct":       pnl_pct,
        })

        reason_label = reason.replace("_", " ").upper()
        emoji  = "✅" if pnl_usdt >= 0 else "❌"
        prefix = "[TESTNET] " if settings.BINANCE_TESTNET else ""

        asyncio.run(send_alert(
            f"{prefix}{emoji} Trade closed — {reason_label}\n\n"
            f"Pair:      {trade['symbol']}\n"
            f"Direction: {'🟢 LONG' if direction == 'BUY' else '🔴 SHORT'}\n"
            f"Entry:     ${entry:,.2f}\n"
            f"Exit:      ${exit_price:,.2f}\n"
            f"PnL:       {pnl_usdt:+.2f} USDT  ({pnl_pct:+.2%})\n\n"
            f"⚠️ Not financial advice."
        ))

    except Exception as exc:
        logger.exception("_close_trade failed (reason={}): {}", reason, exc)
        try:
            asyncio.run(send_alert(f"⚠️ Failed to close position:\n{str(exc)[:200]}"))
        except Exception:
            pass


# ─────────────────────────────────────────────
# Position monitor
# ─────────────────────────────────────────────


def _monitor_position(trade: dict, signal_direction: str) -> None:
    """Check for early exit via signal, then check SL/TP against live price.

    FIX: SELL signal now closes an open BUY position early (model says exit).

    Args:
        trade:            Open trade row from the DB.
        signal_direction: Latest model prediction ('BUY'/'SELL'/'HOLD').
    """
    from bot.execution.trader import get_current_price

    direction = trade["direction"]
    entry     = float(trade["entry_price"])
    sl        = float(trade["stop_loss"])
    tp        = float(trade["take_profit"])

    # 1. Early exit: model flipped to SELL while we hold a long
    if signal_direction == "SELL" and direction == "BUY":
        logger.info("SELL signal while in BUY position — closing early")
        _close_trade(trade, reason="signal")
        return

    # 2. SL/TP check against live price
    try:
        current_price = get_current_price(trade["symbol"])
        logger.info(
            "Position monitor [{} @ {:.2f}]  now={:.2f}  SL={:.2f}  TP={:.2f}",
            direction, entry, current_price, sl, tp,
        )

        hit: str | None = None
        if direction == "BUY":
            if current_price <= sl:
                hit = "stop_loss"
            elif current_price >= tp:
                hit = "take_profit"

        if hit:
            logger.info("{} triggered at {:.2f}", hit.upper(), current_price)
            _close_trade(trade, reason=hit)

    except Exception as exc:
        logger.exception("_monitor_position SL/TP check failed: {}", exc)


# ─────────────────────────────────────────────
# Trade entry
# ─────────────────────────────────────────────


def _execute_entry(sig: dict, levels: dict, signal_id: int) -> None:
    """Open a new long position on the exchange.

    Validates minimum notional before placing the order.

    Args:
        sig:       Signal dict with direction, entry_price, atr, confidence.
        levels:    Risk levels dict with stop_loss, take_profit, risk_reward.
        signal_id: DB id of the saved signal row.
    """
    from bot.execution.trader import get_free_balance, place_market_order

    try:
        balance = get_free_balance("USDT")

        # Guard: minimum position capital
        capital = balance * settings.POSITION_SIZE_PCT
        if capital < _MIN_NOTIONAL_USDT:
            logger.warning(
                "Position capital {:.2f} USDT < Binance minimum notional ({} USDT). "
                "Increase balance or POSITION_SIZE_PCT — skipping trade.",
                capital, _MIN_NOTIONAL_USDT,
            )
            return

        qty  = position_size(balance, sig["entry_price"])
        fill = place_market_order(settings.SYMBOL, "buy", qty)

        trade_id = save_trade({
            "signal_id":      signal_id,
            "symbol":         settings.SYMBOL,
            "direction":      sig["direction"],
            "entry_order_id": fill["order_id"],
            "entry_price":    fill["avg_price"],
            "quantity":       fill["quantity"],
            "notional":       fill["cost"],
            "fee_usdt":       fill["fee_usdt"],
            "stop_loss":      levels["stop_loss"],
            "take_profit":    levels["take_profit"],
        })

        prefix = "[TESTNET] " if settings.BINANCE_TESTNET else ""
        asyncio.run(send_alert(
            f"{prefix}🚀 Trade opened\n\n"
            f"Pair:        {settings.SYMBOL}\n"
            f"Direction:   🟢 LONG\n"
            f"Entry:       ${fill['avg_price']:,.2f}\n"
            f"Quantity:    {fill['quantity']:.6f}\n"
            f"Cost:        ${fill['cost']:.2f} USDT\n"
            f"Stop loss:   ${levels['stop_loss']:,.2f}\n"
            f"Take profit: ${levels['take_profit']:,.2f}\n"
            f"Risk/Reward: 1:{levels['risk_reward']:.1f}\n"
            f"Confidence:  {sig['confidence']:.0%}\n\n"
            f"⚠️ Not financial advice."
        ))
        logger.info("Trade id={} opened", trade_id)

    except Exception as exc:
        logger.exception("_execute_entry failed: {}", exc)
        try:
            asyncio.run(send_alert(f"⚠️ Order execution failed:\n{str(exc)[:200]}"))
        except Exception:
            pass


# ─────────────────────────────────────────────
# Main scheduled job
# ─────────────────────────────────────────────


def run_signal_check() -> None:
    """Core bot cycle — runs every 15 minutes.

    Always generates a model signal so:
    - Open positions can be exited early on a SELL signal
    - SL/TP is also monitored against live price
    - New entries are opened on BUY signals
    """
    try:
        logger.info("─── Signal check ───")

        # 1. Fetch and store fresh candles
        df = fetch_ohlcv(settings.SYMBOL, settings.TIMEFRAME, limit=500)
        inserted = upsert_candles(df)
        logger.info("Candles: {} fetched, {} new", len(df), inserted)

        # 2. Circuit breaker
        if _circuit_breaker_active():
            asyncio.run(send_alert(
                f"⛔ Circuit breaker active — trading paused today.\n"
                f"Max daily loss ({settings.MAX_DAILY_LOSS_PCT:.0%}) exceeded."
            ))
            return

        # 3. Always generate a signal (needed even when in a trade for early exit)
        df_db = get_candles(settings.SYMBOL, settings.TIMEFRAME, limit=500)
        sig   = predict_signal(df_db)

        # 4. If a position is open: monitor it (uses signal for early exit)
        open_trade = get_open_trade(settings.SYMBOL)
        if open_trade:
            _monitor_position(open_trade, sig["direction"])
            return  # Never stack a second position

        # ── No open position below this line ──

        if sig["direction"] == "HOLD":
            logger.info("Signal: HOLD (conf={:.2%}) — skipping", sig["confidence"])
            return

        # 5. Compute risk levels and save signal record
        levels = calculate_levels(sig["direction"], sig["entry_price"], sig["atr"])
        now_ms = int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp() * 1000)
        signal_row = {
            "symbol":       settings.SYMBOL,
            "timestamp":    now_ms,
            "direction":    sig["direction"],
            "confidence":   sig["confidence"],
            "entry_price":  sig["entry_price"],
            "stop_loss":    levels["stop_loss"],
            "take_profit":  levels["take_profit"],
            "risk_reward":  levels["risk_reward"],
            "atr":          sig["atr"],
        }
        signal_id = save_signal(signal_row)

        # 6. Publish signal to Telegram regardless of direction
        published = asyncio.run(publish_signal({**signal_row, "timeframe": settings.TIMEFRAME}))
        if published:
            mark_signal_published(signal_id)

        # 7. Execute only BUY on spot (SELL = publish-only, no shorting)
        if sig["direction"] == "BUY":
            _execute_entry(sig, levels, signal_id)
        else:
            logger.info("SELL signal on spot with no open position — published only (no shorting)")

    except Exception as exc:
        logger.exception("run_signal_check failed: {}", exc)
        try:
            asyncio.run(send_alert(f"⚠️ Bot error in signal check:\n{str(exc)[:200]}"))
        except Exception:
            pass


# ─────────────────────────────────────────────
# Daily summary — uses real closed-trade PnL
# ─────────────────────────────────────────────


def send_daily_summary() -> None:
    """Post yesterday's performance at 07:00 UTC using actual fill data."""
    try:
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()

        signals = get_daily_signals(yesterday)
        all_trades = get_trades(limit=500)

        # Trades closed yesterday
        closed_yesterday = [
            t for t in all_trades
            if t.get("status") == "closed"
            and (t.get("closed_at") or "")[:10] == yesterday
        ]

        wins      = [t for t in closed_yesterday if (t.get("pnl_usdt") or 0) > 0]
        losses    = [t for t in closed_yesterday if (t.get("pnl_usdt") or 0) <= 0]
        total_pnl = sum(float(t.get("pnl_usdt") or 0) for t in closed_yesterday)
        win_rate  = len(wins) / len(closed_yesterday) if closed_yesterday else 0.0

        # pnl_pct for daily_stats: weighted average return across all closed trades
        total_notional = sum(float(t.get("notional") or 0) for t in closed_yesterday)
        pnl_pct = total_pnl / total_notional if total_notional > 0 else 0.0

        # Fallback: use signal-replay estimate if no trades closed
        if not closed_yesterday:
            sig_df     = pd.DataFrame(signals) if signals else pd.DataFrame()
            candles_df = get_candles(settings.SYMBOL, settings.TIMEFRAME, limit=2000)
            outcomes   = evaluate_outcomes(sig_df, candles_df)
            pnl_pct    = outcomes["pnl_pct"]
            win_rate   = outcomes["win_rate"]

        upsert_daily_stats({
            "date":          yesterday,
            "total_signals": len(signals),
            "buy_signals":   sum(1 for s in signals if s["direction"] == "BUY"),
            "sell_signals":  sum(1 for s in signals if s["direction"] == "SELL"),
            "pnl_pct":       pnl_pct,
            "win_rate":      win_rate,
        })

        prefix    = "[TESTNET] " if settings.BINANCE_TESTNET else ""
        pnl_emoji = "🟢" if total_pnl >= 0 else "🔴"
        pnl_src   = "actual fills" if closed_yesterday else "signal replay estimate"

        asyncio.run(send_alert(
            f"{prefix}📊 Daily Summary — {yesterday}\n\n"
            f"Signals:       {len(signals)} "
            f"({sum(1 for s in signals if s['direction']=='BUY')} BUY · "
            f"{sum(1 for s in signals if s['direction']=='SELL')} SELL)\n\n"
            f"Trades closed: {len(closed_yesterday)}\n"
            f"Wins / Losses: {len(wins)} / {len(losses)}\n"
            f"Win rate:      {win_rate:.0%}\n"
            f"Realized PnL:  {pnl_emoji} {total_pnl:+.2f} USDT\n\n"
            f"⚠️ PnL from {pnl_src}. Not financial advice."
        ))
        logger.info("Daily summary sent for {}", yesterday)

    except Exception as exc:
        logger.exception("send_daily_summary failed: {}", exc)
        try:
            asyncio.run(send_alert(f"⚠️ Daily summary error:\n{str(exc)[:200]}"))
        except Exception:
            pass


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────


def main() -> None:
    _setup_logging()
    _check_prerequisites()

    mode = "TESTNET" if settings.BINANCE_TESTNET else "⚠️  LIVE — REAL FUNDS"
    logger.info("Starting TradingBot [{}] — {}/{}", mode, settings.SYMBOL, settings.TIMEFRAME)
    logger.info(
        "Threshold: {:.0%} | Position: {:.0%} | Max loss: {:.0%}",
        settings.SIGNAL_THRESHOLD, settings.POSITION_SIZE_PCT, settings.MAX_DAILY_LOSS_PCT,
    )

    try:
        asyncio.run(send_alert(
            f"{'[TESTNET] ' if settings.BINANCE_TESTNET else '⚠️ LIVE — '}🤖 Bot started.\n"
            f"Symbol: {settings.SYMBOL}  |  TF: {settings.TIMEFRAME}  |  "
            f"Threshold: {settings.SIGNAL_THRESHOLD:.0%}"
        ))
    except Exception as exc:
        logger.warning("Startup Telegram ping failed: {}", exc)

    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        run_signal_check,
        trigger=IntervalTrigger(minutes=15),
        id="signal_check",
        name="Signal Check",
        misfire_grace_time=60,
        max_instances=1,
    )
    scheduler.add_job(
        send_daily_summary,
        trigger=CronTrigger(hour=7, minute=0, timezone="UTC"),
        id="daily_summary",
        name="Daily Summary",
        misfire_grace_time=300,
        max_instances=1,
    )
    scheduler.start()

    logger.info("Running first signal check now…")
    run_signal_check()

    def _shutdown(signum, frame):
        logger.info("Shutdown signal received.")
        scheduler.shutdown(wait=False)
        try:
            asyncio.run(send_alert("🛑 Bot stopped."))
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    logger.info("Bot running — Ctrl+C to stop.")
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
