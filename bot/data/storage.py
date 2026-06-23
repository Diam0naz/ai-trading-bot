"""SQLite read/write via SQLAlchemy. WAL mode enabled on every connection.

The Python bot is the sole writer. Next.js reads via better-sqlite3 (read-only).
"""

from __future__ import annotations

import datetime
from typing import Any

import pandas as pd
from loguru import logger
from sqlalchemy import create_engine, event, text

from bot.config.settings import settings

_engine = None


def _get_engine():
    """Return the singleton SQLAlchemy engine, enabling WAL on first connection."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            f"sqlite:///{settings.DATABASE_PATH}",
            echo=False,
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(_engine, "connect")
        def _set_wal(dbapi_conn, _record):
            dbapi_conn.execute("PRAGMA journal_mode=WAL")
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

        logger.info("SQLite engine created: {}", settings.DATABASE_PATH)
    return _engine


# ─────────────────────────────────────────────
# Candles
# ─────────────────────────────────────────────


def upsert_candles(df: pd.DataFrame) -> int:
    """Bulk insert candles, skipping rows that violate the UNIQUE constraint.

    Args:
        df: DataFrame with columns [symbol, timeframe, timestamp, open, high,
            low, close, volume]. timestamp must be Unix ms integers.

    Returns:
        Number of rows actually inserted.
    """
    if df.empty:
        return 0

    required = ["symbol", "timeframe", "timestamp", "open", "high", "low", "close", "volume"]
    records = df[required].to_dict(orient="records")
    # Coerce numpy types → native Python (sqlite3 cannot adapt numpy scalars)
    clean = []
    for r in records:
        clean.append({
            "symbol": str(r["symbol"]),
            "timeframe": str(r["timeframe"]),
            "timestamp": int(r["timestamp"]),
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": float(r["close"]),
            "volume": float(r["volume"]),
        })

    try:
        with _get_engine().begin() as conn:
            result = conn.execute(
                text("""
                    INSERT OR IGNORE INTO candles
                        (symbol, timeframe, timestamp, open, high, low, close, volume)
                    VALUES
                        (:symbol, :timeframe, :timestamp, :open, :high, :low, :close, :volume)
                """),
                clean,
            )
            inserted = result.rowcount
        logger.debug("upsert_candles: {} inserted, {} skipped", inserted, len(clean) - inserted)
        return inserted
    except Exception as exc:
        logger.error("upsert_candles failed: {}", exc)
        raise


def get_candles(symbol: str, timeframe: str, limit: int = 500) -> pd.DataFrame:
    """Return most recent candles ordered ascending (oldest first) for indicators.

    Args:
        symbol:    Trading pair.
        timeframe: Candle interval.
        limit:     Maximum rows to return.

    Returns:
        DataFrame with columns [timestamp, open, high, low, close, volume].
    """
    try:
        with _get_engine().connect() as conn:
            df = pd.read_sql(
                text("""
                    SELECT timestamp, open, high, low, close, volume
                    FROM candles
                    WHERE symbol = :symbol AND timeframe = :timeframe
                    ORDER BY timestamp DESC
                    LIMIT :limit
                """),
                conn,
                params={"symbol": symbol, "timeframe": timeframe, "limit": limit},
            )
        df = df.sort_values("timestamp").reset_index(drop=True)
        logger.debug("get_candles: {} rows for {}/{}", len(df), symbol, timeframe)
        return df
    except Exception as exc:
        logger.error("get_candles failed: {}", exc)
        raise


# ─────────────────────────────────────────────
# Signals
# ─────────────────────────────────────────────


def save_signal(signal: dict[str, Any]) -> int:
    """Insert a signal row and return the new auto-generated id.

    Args:
        signal: Dict with keys: symbol, timestamp, direction, confidence,
                entry_price, stop_loss, take_profit, risk_reward, atr.

    Returns:
        Inserted row id.
    """
    try:
        with _get_engine().begin() as conn:
            result = conn.execute(
                text("""
                    INSERT INTO signals
                        (symbol, timestamp, direction, confidence, entry_price,
                         stop_loss, take_profit, risk_reward, atr)
                    VALUES
                        (:symbol, :timestamp, :direction, :confidence, :entry_price,
                         :stop_loss, :take_profit, :risk_reward, :atr)
                """),
                {
                    "symbol": str(signal["symbol"]),
                    "timestamp": int(signal["timestamp"]),
                    "direction": str(signal["direction"]),
                    "confidence": float(signal["confidence"]),
                    "entry_price": float(signal["entry_price"]),
                    "stop_loss": float(signal["stop_loss"]) if signal.get("stop_loss") is not None else None,
                    "take_profit": float(signal["take_profit"]) if signal.get("take_profit") is not None else None,
                    "risk_reward": float(signal["risk_reward"]) if signal.get("risk_reward") is not None else None,
                    "atr": float(signal["atr"]) if signal.get("atr") is not None else None,
                },
            )
            signal_id = result.lastrowid
        logger.info("Signal saved id={} dir={} conf={:.2%}", signal_id, signal["direction"], float(signal["confidence"]))
        return signal_id
    except Exception as exc:
        logger.error("save_signal failed: {}", exc)
        raise


def mark_signal_published(signal_id: int) -> None:
    """Set published=1 for the given signal id.

    Args:
        signal_id: Primary key of the signal row.
    """
    try:
        with _get_engine().begin() as conn:
            conn.execute(
                text("UPDATE signals SET published=1 WHERE id=:id"),
                {"id": signal_id},
            )
        logger.debug("Signal {} marked published", signal_id)
    except Exception as exc:
        logger.error("mark_signal_published failed id={}: {}", signal_id, exc)
        raise


def get_signals(limit: int = 50, symbol: str | None = None) -> list[dict]:
    """Return most recent signals ordered newest first.

    Args:
        limit:  Maximum rows (capped at 100 for safety).
        symbol: Optional symbol filter.

    Returns:
        List of signal dicts.
    """
    limit = min(limit, 100)
    try:
        with _get_engine().connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT * FROM signals
                    WHERE (:symbol IS NULL OR symbol = :symbol)
                    ORDER BY timestamp DESC
                    LIMIT :limit
                """),
                {"symbol": symbol, "limit": limit},
            ).mappings().all()
        return [dict(r) for r in rows]
    except Exception as exc:
        logger.error("get_signals failed: {}", exc)
        raise


def get_daily_signals(date_str: str) -> list[dict]:
    """Return all signals created on a given calendar date (UTC).

    Args:
        date_str: Date in 'YYYY-MM-DD' format.

    Returns:
        List of signal dicts ordered ascending by timestamp.
    """
    try:
        with _get_engine().connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT * FROM signals
                    WHERE date(created_at) = :date
                    ORDER BY timestamp ASC
                """),
                {"date": date_str},
            ).mappings().all()
        return [dict(r) for r in rows]
    except Exception as exc:
        logger.error("get_daily_signals failed date={}: {}", date_str, exc)
        raise


# ─────────────────────────────────────────────
# Daily stats
# ─────────────────────────────────────────────


def upsert_daily_stats(stats: dict) -> None:
    """Insert or replace a daily_stats row for the given date.

    Args:
        stats: Dict with keys: date, total_signals, buy_signals, sell_signals,
               pnl_pct, win_rate. Optional: starting_balance, ending_balance.
    """
    try:
        with _get_engine().begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO daily_stats
                        (date, starting_balance, ending_balance,
                         total_signals, buy_signals, sell_signals, pnl_pct, win_rate)
                    VALUES
                        (:date, :starting_balance, :ending_balance,
                         :total_signals, :buy_signals, :sell_signals, :pnl_pct, :win_rate)
                    ON CONFLICT(date) DO UPDATE SET
                        total_signals = excluded.total_signals,
                        buy_signals   = excluded.buy_signals,
                        sell_signals  = excluded.sell_signals,
                        pnl_pct       = excluded.pnl_pct,
                        win_rate      = excluded.win_rate
                """),
                {
                    "date": str(stats["date"]),
                    "starting_balance": stats.get("starting_balance"),
                    "ending_balance": stats.get("ending_balance"),
                    "total_signals": int(stats.get("total_signals", 0)),
                    "buy_signals": int(stats.get("buy_signals", 0)),
                    "sell_signals": int(stats.get("sell_signals", 0)),
                    "pnl_pct": float(stats.get("pnl_pct", 0.0)),
                    "win_rate": float(stats.get("win_rate", 0.0)),
                },
            )
        logger.debug("daily_stats upserted for {}", stats["date"])
    except Exception as exc:
        logger.error("upsert_daily_stats failed: {}", exc)
        raise


def get_daily_stats(days: int = 30) -> list[dict]:
    """Return last N days of daily_stats ordered by date ascending.

    Args:
        days: Number of days to return.

    Returns:
        List of daily_stats dicts, oldest first.
    """
    try:
        with _get_engine().connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT * FROM daily_stats
                    ORDER BY date DESC
                    LIMIT :days
                """),
                {"days": days},
            ).mappings().all()
        return list(reversed([dict(r) for r in rows]))
    except Exception as exc:
        logger.error("get_daily_stats failed: {}", exc)
        raise


def get_today_pnl() -> float | None:
    """Return today's pnl_pct from daily_stats, or None if no row exists yet.

    Returns:
        PnL fraction (e.g. -0.06) or None.
    """
    today = datetime.date.today().isoformat()
    try:
        with _get_engine().connect() as conn:
            row = conn.execute(
                text("SELECT pnl_pct FROM daily_stats WHERE date = :date"),
                {"date": today},
            ).fetchone()
        return float(row[0]) if row else None
    except Exception as exc:
        logger.error("get_today_pnl failed: {}", exc)
        return None


# ─────────────────────────────────────────────
# Trades
# ─────────────────────────────────────────────


def save_trade(trade: dict[str, Any]) -> int:
    """Insert a new open trade row and return its id.

    Args:
        trade: Dict with keys: signal_id, symbol, direction, entry_order_id,
               entry_price, quantity, notional, fee_usdt, stop_loss, take_profit.

    Returns:
        Inserted trade id.
    """
    try:
        with _get_engine().begin() as conn:
            result = conn.execute(
                text("""
                    INSERT INTO trades
                        (signal_id, symbol, direction, entry_order_id,
                         entry_price, quantity, notional, fee_usdt,
                         stop_loss, take_profit)
                    VALUES
                        (:signal_id, :symbol, :direction, :entry_order_id,
                         :entry_price, :quantity, :notional, :fee_usdt,
                         :stop_loss, :take_profit)
                """),
                {
                    "signal_id":       trade.get("signal_id"),
                    "symbol":          str(trade["symbol"]),
                    "direction":       str(trade["direction"]),
                    "entry_order_id":  trade.get("entry_order_id"),
                    "entry_price":     float(trade["entry_price"]),
                    "quantity":        float(trade["quantity"]),
                    "notional":        float(trade["notional"]),
                    "fee_usdt":        float(trade.get("fee_usdt", 0.0)),
                    "stop_loss":       float(trade["stop_loss"]),
                    "take_profit":     float(trade["take_profit"]),
                },
            )
            trade_id = result.lastrowid
        logger.info(
            "Trade opened id={} {} {} qty={:.6f} @ {:.2f}",
            trade_id, trade["direction"], trade["symbol"],
            float(trade["quantity"]), float(trade["entry_price"]),
        )
        return trade_id
    except Exception as exc:
        logger.error("save_trade failed: {}", exc)
        raise


def get_open_trade(symbol: str) -> dict | None:
    """Return the current open trade for a symbol, or None.

    Args:
        symbol: Trading pair.

    Returns:
        Trade dict or None if no open position exists.
    """
    try:
        with _get_engine().connect() as conn:
            row = conn.execute(
                text("""
                    SELECT * FROM trades
                    WHERE symbol = :symbol AND status = 'open'
                    ORDER BY opened_at DESC LIMIT 1
                """),
                {"symbol": symbol},
            ).mappings().fetchone()
        return dict(row) if row else None
    except Exception as exc:
        logger.error("get_open_trade failed: {}", exc)
        raise


def close_trade_record(trade_id: int, exit_info: dict) -> None:
    """Update a trade row with exit fill details and mark it closed.

    Args:
        trade_id:  Primary key of the trade row.
        exit_info: Dict with keys: exit_order_id, exit_price, exit_reason,
                   pnl_usdt, pnl_pct.
    """
    try:
        with _get_engine().begin() as conn:
            conn.execute(
                text("""
                    UPDATE trades SET
                        status        = 'closed',
                        exit_order_id = :exit_order_id,
                        exit_price    = :exit_price,
                        exit_reason   = :exit_reason,
                        pnl_usdt      = :pnl_usdt,
                        pnl_pct       = :pnl_pct,
                        closed_at     = datetime('now')
                    WHERE id = :trade_id
                """),
                {
                    "trade_id":      trade_id,
                    "exit_order_id": exit_info.get("exit_order_id"),
                    "exit_price":    float(exit_info["exit_price"]),
                    "exit_reason":   str(exit_info["exit_reason"]),
                    "pnl_usdt":      float(exit_info["pnl_usdt"]),
                    "pnl_pct":       float(exit_info["pnl_pct"]),
                },
            )
        logger.info(
            "Trade closed id={} reason={} pnl={:+.2f} USDT ({:+.2%})",
            trade_id, exit_info["exit_reason"],
            float(exit_info["pnl_usdt"]), float(exit_info["pnl_pct"]),
        )
    except Exception as exc:
        logger.error("close_trade_record failed id={}: {}", trade_id, exc)
        raise


def get_trades(limit: int = 50) -> list[dict]:
    """Return recent trades ordered newest first (open trades first, then closed).

    Args:
        limit: Maximum rows to return.

    Returns:
        List of trade dicts.
    """
    try:
        with _get_engine().connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT * FROM trades
                    ORDER BY
                        CASE status WHEN 'open' THEN 0 ELSE 1 END ASC,
                        opened_at DESC
                    LIMIT :limit
                """),
                {"limit": limit},
            ).mappings().all()
        return [dict(r) for r in rows]
    except Exception as exc:
        logger.error("get_trades failed: {}", exc)
        raise


def get_today_realized_pnl() -> float | None:
    """Return today's realized PnL from closed trades (USDT).

    Used by the circuit breaker for real P&L rather than estimated.

    Returns:
        Sum of pnl_usdt for trades closed today, or None if no closed trades.
    """
    today = datetime.date.today().isoformat()
    try:
        with _get_engine().connect() as conn:
            row = conn.execute(
                text("""
                    SELECT SUM(pnl_usdt) as total, COUNT(*) as cnt
                    FROM trades
                    WHERE status = 'closed'
                      AND date(closed_at) = :today
                """),
                {"today": today},
            ).fetchone()
        if row and row[1] and row[1] > 0:
            return float(row[0])
        return None
    except Exception as exc:
        logger.error("get_today_realized_pnl failed: {}", exc)
        return None
