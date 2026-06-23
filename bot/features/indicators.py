"""Technical indicator computation via pandas-ta.

All indicator columns are renamed to simple snake_case names so the rest of the
codebase does not depend on pandas-ta's internal naming conventions.
"""

from __future__ import annotations

import pandas as pd
import pandas_ta  # registers the .ta accessor on DataFrame
from loguru import logger


# Columns added by compute_indicators — exported so consumers can reference them.
INDICATOR_COLS = [
    "rsi", "macd", "macd_signal", "macd_hist",
    "bb_upper", "bb_mid", "bb_lower", "bb_position",
    "atr", "ema20", "ema50", "ema_ratio",
    "vol_sma", "vol_ratio", "returns",
]


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Compute all technical indicators and derived features.

    Appends the following columns (all renamed from pandas-ta defaults):
      rsi          — RSI 14
      macd         — MACD line (12, 26, 9)
      macd_signal  — MACD signal line
      macd_hist    — MACD histogram
      bb_upper     — Bollinger upper band (20, 2σ)
      bb_mid       — Bollinger middle band
      bb_lower     — Bollinger lower band
      bb_position  — (close − bb_lower) / (bb_upper − bb_lower), clipped 0–1
      atr          — ATR 14 (price units)
      ema20        — EMA 20
      ema50        — EMA 50
      ema_ratio    — ema20 / ema50
      vol_sma      — Volume SMA 20
      vol_ratio    — volume / vol_sma
      returns      — close.pct_change()

    Rows with NaN (indicator warm-up) are dropped before returning.

    Args:
        df: DataFrame with at least [timestamp, open, high, low, close, volume].

    Returns:
        Enriched DataFrame with all indicator columns; NaN rows removed.
    """
    df = df.copy()

    # ── Momentum ──────────────────────────────
    df["rsi"] = df.ta.rsi(length=14)

    macd_df = df.ta.macd(fast=12, slow=26, signal=9)
    df["macd"] = macd_df["MACD_12_26_9"]
    df["macd_signal"] = macd_df["MACDs_12_26_9"]
    df["macd_hist"] = macd_df["MACDh_12_26_9"]

    # ── Volatility ────────────────────────────
    bb_df = df.ta.bbands(length=20, std=2)
    # Column names changed in pandas-ta 0.4.x: BBU_20_2.0 → BBU_20_2.0_2.0
    bb_cols = bb_df.columns.tolist()
    upper_col = next(c for c in bb_cols if c.startswith("BBU"))
    mid_col   = next(c for c in bb_cols if c.startswith("BBM"))
    lower_col = next(c for c in bb_cols if c.startswith("BBL"))
    df["bb_upper"] = bb_df[upper_col]
    df["bb_mid"]   = bb_df[mid_col]
    df["bb_lower"] = bb_df[lower_col]

    df["atr"] = df.ta.atr(length=14)

    # ── Trend ─────────────────────────────────
    df["ema20"] = df.ta.ema(length=20)
    df["ema50"] = df.ta.ema(length=50)

    # ── Volume ────────────────────────────────
    df["vol_sma"] = df["volume"].rolling(window=20).mean()

    # ── Derived features ──────────────────────
    band_range = (df["bb_upper"] - df["bb_lower"]).replace(0.0, float("nan"))
    df["bb_position"] = ((df["close"] - df["bb_lower"]) / band_range).clip(0.0, 1.0)

    df["ema_ratio"] = df["ema20"] / df["ema50"].replace(0.0, float("nan"))

    df["vol_ratio"] = df["volume"] / df["vol_sma"].replace(0.0, float("nan"))

    df["returns"] = df["close"].pct_change()

    # ── Drop warm-up NaN rows ─────────────────
    before = len(df)
    df.dropna(inplace=True)
    df.reset_index(drop=True, inplace=True)

    logger.debug(
        "Indicators computed: {} rows kept, {} dropped (warm-up)",
        len(df), before - len(df),
    )
    return df
