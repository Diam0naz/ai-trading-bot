"""Forward-looking label generation for supervised training.

HOLD rows are dropped entirely — the model trains only on clear BUY/SELL cases.
"""

from __future__ import annotations

import pandas as pd
from loguru import logger

LABEL_SELL = 0
LABEL_BUY = 1


def generate_labels(
    df: pd.DataFrame,
    forward_candles: int = 4,
    threshold: float = 0.003,
) -> pd.DataFrame:
    """Attach BUY/SELL labels based on future price movement, dropping HOLD rows.

    For each candle at index i:
        future_return = (close[i + forward_candles] - close[i]) / close[i]

    Labels:
        1 (BUY)  — future_return >  +threshold
        0 (SELL) — future_return < -threshold
        HOLD rows are removed — the model is trained as a binary classifier.

    Args:
        df:              DataFrame with at least a 'close' column.
        forward_candles: Lookahead window in candles.
        threshold:       Minimum price move to be considered directional (0.3%).

    Returns:
        DataFrame with 'label' column (0 or 1 only); tail rows and HOLD rows removed.
    """
    df = df.copy()

    future_close = df["close"].shift(-forward_candles)
    future_return = (future_close - df["close"]) / df["close"]

    # Keep only rows where future data exists
    df = df[~future_return.isna()].copy()
    future_return = future_return[~future_return.isna()]

    df["label"] = None
    df.loc[future_return > threshold, "label"] = LABEL_BUY
    df.loc[future_return < -threshold, "label"] = LABEL_SELL

    # Drop HOLD rows (label still None)
    before = len(df)
    df = df[df["label"].notna()].copy()
    df["label"] = df["label"].astype(int)
    df.reset_index(drop=True, inplace=True)

    hold_dropped = before - len(df)
    buy_count = (df["label"] == LABEL_BUY).sum()
    sell_count = (df["label"] == LABEL_SELL).sum()

    logger.info(
        "Labels: BUY={} SELL={} (HOLD dropped={})",
        buy_count, sell_count, hold_dropped,
    )
    return df
