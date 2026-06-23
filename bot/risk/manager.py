"""Position sizing, stop-loss/take-profit calculation, circuit breaker, and PnL replay."""

from __future__ import annotations

import pandas as pd
from loguru import logger

from bot.config.settings import settings


# ─────────────────────────────────────────────
# Trade levels
# ─────────────────────────────────────────────


def calculate_levels(direction: str, entry_price: float, atr: float) -> dict:
    """Compute stop-loss, take-profit, and risk/reward ratio from ATR.

    BUY:  stop_loss = entry - atr * SL_mult  |  take_profit = entry + atr * TP_mult
    SELL: stop_loss = entry + atr * SL_mult  |  take_profit = entry - atr * TP_mult

    Args:
        direction:   "BUY" or "SELL".
        entry_price: Trade entry price.
        atr:         Average True Range for the current candle.

    Returns:
        Dict with keys: stop_loss (float), take_profit (float), risk_reward (float).
    """
    sl_dist = atr * settings.ATR_MULTIPLIER_SL
    tp_dist = atr * settings.ATR_MULTIPLIER_TP

    if direction == "BUY":
        stop_loss = entry_price - sl_dist
        take_profit = entry_price + tp_dist
    elif direction == "SELL":
        stop_loss = entry_price + sl_dist
        take_profit = entry_price - tp_dist
    else:
        raise ValueError(f"direction must be 'BUY' or 'SELL', got '{direction}'")

    risk = abs(entry_price - stop_loss)
    reward = abs(take_profit - entry_price)
    risk_reward = round(reward / risk, 4) if risk > 0 else 0.0

    logger.debug(
        "Levels [{}] entry={:.2f} SL={:.2f} TP={:.2f} RR=1:{:.2f}",
        direction, entry_price, stop_loss, take_profit, risk_reward,
    )
    return {
        "stop_loss": round(stop_loss, 8),
        "take_profit": round(take_profit, 8),
        "risk_reward": risk_reward,
    }


# ─────────────────────────────────────────────
# Circuit breaker
# ─────────────────────────────────────────────


def check_circuit_breaker() -> bool:
    """Return True if today's PnL has breached the maximum daily loss threshold.

    Queries today's daily_stats row from the DB. Returns False if no row exists yet.

    Returns:
        True  → halt signal publishing for the rest of the day.
        False → safe to continue.
    """
    from bot.data.storage import get_today_pnl  # local import avoids circular at module load

    pnl = get_today_pnl()
    if pnl is None:
        return False

    if pnl < -settings.MAX_DAILY_LOSS_PCT:
        logger.warning(
            "Circuit breaker: today pnl={:.2%} < -{:.0%} threshold",
            pnl, settings.MAX_DAILY_LOSS_PCT,
        )
        return True
    return False


# ─────────────────────────────────────────────
# Position sizing
# ─────────────────────────────────────────────


def position_size(balance: float, entry_price: float) -> float:
    """Return trade quantity using fixed-fractional position sizing.

    quantity = (balance × POSITION_SIZE_PCT) / entry_price

    Args:
        balance:     Total account balance in quote currency.
        entry_price: Current asset price.

    Returns:
        Quantity of base asset to trade.
    """
    if entry_price <= 0:
        raise ValueError(f"entry_price must be positive, got {entry_price}")
    qty = (balance * settings.POSITION_SIZE_PCT) / entry_price
    logger.debug("Position size: balance={:.2f} → qty={:.6f} @ {:.2f}", balance, qty, entry_price)
    return qty


# ─────────────────────────────────────────────
# Outcome evaluation (PnL replay)
# ─────────────────────────────────────────────


def evaluate_outcomes(
    signals_df: pd.DataFrame,
    candles_df: pd.DataFrame,
    max_horizon: int = 96,
) -> dict:
    """Replay published signals against subsequent candles to compute realized PnL.

    For each BUY/SELL signal, scans forward candles for the first TP/SL touch.
    SL takes priority when both levels are straddled by a single candle.
    Trades unresolved within max_horizon are counted as open (0 PnL contribution).

    Account-level PnL per trade = price_move_fraction × POSITION_SIZE_PCT.

    Args:
        signals_df:  Signal rows (needs direction, entry_price, stop_loss,
                     take_profit, timestamp as Unix ms integers).
        candles_df:  OHLCV candles (needs timestamp, high, low) ordered ascending.
        max_horizon: Max candles to look ahead.

    Returns:
        Dict: total_trades, winning_trades, losing_trades, open_trades,
        win_rate (decimal), pnl_pct (account-level decimal fraction).
    """
    result = {"total_trades": 0, "winning_trades": 0, "losing_trades": 0,
              "open_trades": 0, "win_rate": 0.0, "pnl_pct": 0.0}

    if signals_df is None or candles_df is None or len(signals_df) == 0 or len(candles_df) == 0:
        return result

    candles = candles_df.copy().sort_values("timestamp").reset_index(drop=True)
    c_ts = candles["timestamp"].astype(int)
    pnl_total = 0.0

    actionable = signals_df[signals_df["direction"].isin(["BUY", "SELL"])]

    for _, sig in actionable.iterrows():
        entry = sig.get("entry_price")
        sl = sig.get("stop_loss")
        tp = sig.get("take_profit")
        if any(v is None or pd.isna(v) for v in [entry, sl, tp]):
            continue

        entry, sl, tp = float(entry), float(sl), float(tp)
        direction = sig["direction"]
        sig_ts = int(sig["timestamp"])

        future = candles[c_ts > sig_ts].head(max_horizon)
        if future.empty:
            result["open_trades"] += 1
            result["total_trades"] += 1
            continue

        outcome = None
        for _, candle in future.iterrows():
            hi, lo = float(candle["high"]), float(candle["low"])
            if direction == "BUY":
                if lo <= sl:
                    outcome = "loss"; break
                if hi >= tp:
                    outcome = "win"; break
            else:  # SELL
                if hi >= sl:
                    outcome = "loss"; break
                if lo <= tp:
                    outcome = "win"; break

        result["total_trades"] += 1
        if outcome == "win":
            result["winning_trades"] += 1
            move = (tp - entry) / entry if direction == "BUY" else (entry - tp) / entry
            pnl_total += move * settings.POSITION_SIZE_PCT
        elif outcome == "loss":
            result["losing_trades"] += 1
            move = (sl - entry) / entry if direction == "BUY" else (entry - sl) / entry
            pnl_total += move * settings.POSITION_SIZE_PCT
        else:
            result["open_trades"] += 1

    closed = result["winning_trades"] + result["losing_trades"]
    result["win_rate"] = result["winning_trades"] / closed if closed else 0.0
    result["pnl_pct"] = pnl_total

    logger.debug(
        "Outcomes: {} trades  {}/{} win/loss  {} open  win_rate={:.0%}  pnl={:.2%}",
        result["total_trades"], result["winning_trades"], result["losing_trades"],
        result["open_trades"], result["win_rate"], result["pnl_pct"],
    )
    return result
