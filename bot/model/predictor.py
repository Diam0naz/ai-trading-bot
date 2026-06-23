"""Signal prediction — loads the XGBoost model once and runs inference.

Singleton pattern: the model is loaded from disk on first import and reused.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from loguru import logger

from bot.config.settings import settings
from bot.features.indicators import compute_indicators
from bot.model.trainer import FEATURE_COLS, load_model

# ── Model singleton ────────────────────────────────────────────────────────────
_model = None


def _get_model():
    global _model
    if _model is None:
        _model = load_model()   # raises FileNotFoundError with clear message if missing
    return _model


# ── Class mapping (binary: HOLD rows were dropped during training) ─────────────
_LABEL_MAP = {0: "SELL", 1: "BUY"}


def predict_signal(df: pd.DataFrame) -> dict:
    """Generate a trading signal from raw OHLCV data.

    Steps:
        1. compute_indicators(df)
        2. Extract FEATURE_COLS from the last row
        3. model.predict_proba() → per-class confidence
        4. If max confidence < SIGNAL_THRESHOLD → HOLD
        5. Map winning class to direction: 0 → SELL, 1 → BUY

    Args:
        df: Raw OHLCV DataFrame (≥100 rows recommended for warm-up).
            Columns: timestamp, open, high, low, close, volume.

    Returns:
        Dict with keys:
          direction   (str):   "BUY" | "SELL" | "HOLD"
          confidence  (float): max class probability
          entry_price (float | None): latest close (None for HOLD)
          atr         (float | None): latest ATR  (None for HOLD)
    """
    model = _get_model()

    enriched = compute_indicators(df)
    if enriched.empty:
        logger.warning("predict_signal: no rows after indicator computation")
        return _hold(0.0)

    missing = [c for c in FEATURE_COLS if c not in enriched.columns]
    if missing:
        logger.warning("predict_signal: missing columns {}", missing)
        return _hold(0.0)

    last = enriched.iloc[-1]
    if last[FEATURE_COLS].isna().any():
        logger.warning("predict_signal: NaN in last-row features")
        return _hold(0.0)

    X = last[FEATURE_COLS].values.astype(np.float64).reshape(1, -1)

    proba = model.predict_proba(X)[0]          # shape: (n_classes,)
    class_idx = int(np.argmax(proba))
    confidence = float(proba[class_idx])

    # model.classes_ is the actual label array, e.g. [0, 1]
    predicted_class = int(model.classes_[class_idx])
    direction = _LABEL_MAP.get(predicted_class, "HOLD")

    logger.info(
        "Prediction: {} conf={:.2%} (threshold={:.0%})",
        direction, confidence, settings.SIGNAL_THRESHOLD,
    )

    if confidence < settings.SIGNAL_THRESHOLD:
        return _hold(confidence)

    return {
        "direction": direction,
        "confidence": confidence,
        "entry_price": float(last["close"]),
        "atr": float(last["atr"]),
    }


def _hold(confidence: float) -> dict:
    return {"direction": "HOLD", "confidence": confidence, "entry_price": None, "atr": None}
