"""XGBoost model training with walk-forward validation.

Run as:
    python -m bot.model.trainer
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Tuple

import joblib
import numpy as np
import pandas as pd
from loguru import logger
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from xgboost import XGBClassifier

from bot.config.settings import settings
from bot.data.storage import get_candles
from bot.features.indicators import compute_indicators
from bot.model.labels import generate_labels

# Feature columns — exact order used for both training and inference.
FEATURE_COLS = [
    "rsi",
    "macd_hist",
    "bb_position",
    "atr",
    "ema_ratio",
    "vol_ratio",
    "returns",
]


# ─────────────────────────────────────────────
# Feature extraction
# ─────────────────────────────────────────────


def prepare_features(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    """Extract feature matrix X and label vector y from an enriched DataFrame.

    compute_indicators() must already have been called; all FEATURE_COLS and
    'label' must be present.

    Args:
        df: Labelled DataFrame with indicator columns.

    Returns:
        (X, y) as float64 / int numpy arrays.
    """
    missing = [c for c in FEATURE_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing feature columns: {missing}")

    df = df.dropna(subset=FEATURE_COLS).copy()
    X = df[FEATURE_COLS].values.astype(np.float64)
    y = df["label"].values.astype(int)
    return X, y


# ─────────────────────────────────────────────
# Training
# ─────────────────────────────────────────────


def _build_model() -> XGBClassifier:
    # use_label_encoder removed in xgboost 2.0
    return XGBClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1,
    )


def train_model(X: np.ndarray, y: np.ndarray, n_folds: int = 5) -> XGBClassifier:
    """Train XGBoost with sequential walk-forward validation (no data leakage).

    Each fold trains on all data up to the fold boundary and tests on the next
    chunk. Never trains on future data.

    Args:
        X:       Feature matrix (n_samples, n_features).
        y:       Binary label vector — 0=SELL, 1=BUY.
        n_folds: Number of walk-forward folds.

    Returns:
        Model refitted on the full dataset after validation.
    """
    n = len(X)
    fold_size = n // (n_folds + 1)

    print("\n" + "=" * 68)
    print(f"Walk-Forward Validation  ({n_folds} folds, {n} samples, {len(FEATURE_COLS)} features)")
    print("=" * 68)

    accs, f1s, precs, recs = [], [], [], []

    for fold in range(1, n_folds + 1):
        train_end = fold * fold_size
        test_start = train_end
        test_end = min(test_start + fold_size, n)

        if test_start >= n:
            break

        X_tr, y_tr = X[:train_end], y[:train_end]
        X_te, y_te = X[test_start:test_end], y[test_start:test_end]

        mdl = _build_model()
        mdl.fit(X_tr, y_tr, eval_set=[(X_te, y_te)], verbose=False)
        y_pred = mdl.predict(X_te)

        acc = accuracy_score(y_te, y_pred)
        prec = precision_score(y_te, y_pred, average="binary", zero_division=0)
        rec = recall_score(y_te, y_pred, average="binary", zero_division=0)
        f1 = f1_score(y_te, y_pred, average="binary", zero_division=0)

        accs.append(acc); f1s.append(f1); precs.append(prec); recs.append(rec)

        print(
            f"  Fold {fold}/{n_folds}  train={train_end:>5}  test={len(y_te):>4}"
            f"  acc={acc:.3f}  prec={prec:.3f}  rec={rec:.3f}  f1={f1:.3f}"
        )

    print("-" * 68)
    print(
        f"  Mean  acc={np.mean(accs):.3f}±{np.std(accs):.3f}"
        f"  prec={np.mean(precs):.3f}  rec={np.mean(recs):.3f}  f1={np.mean(f1s):.3f}"
    )
    print("=" * 68)

    print("\nRefitting on full dataset…")
    final = _build_model()
    final.fit(X, y, verbose=False)
    print("Done.\n")
    return final


# ─────────────────────────────────────────────
# Serialization
# ─────────────────────────────────────────────


def save_model(model: XGBClassifier, path: str | None = None) -> None:
    """Serialize model to disk with joblib.

    Args:
        model: Trained XGBClassifier.
        path:  Destination path (defaults to settings.MODEL_PATH).
    """
    p = Path(path or settings.MODEL_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, p)
    logger.info("Model saved: {}", p)


def load_model(path: str | None = None) -> XGBClassifier:
    """Deserialize model from disk.

    Args:
        path: Source path (defaults to settings.MODEL_PATH).

    Returns:
        Loaded XGBClassifier.

    Raises:
        FileNotFoundError: If the model file does not exist.
    """
    p = Path(path or settings.MODEL_PATH)
    if not p.exists():
        raise FileNotFoundError(
            f"Model not found at {p}. Run: python -m bot.model.trainer"
        )
    model = joblib.load(p)
    logger.info("Model loaded: {}", p)
    return model


# ─────────────────────────────────────────────
# CLI entrypoint
# ─────────────────────────────────────────────


def main() -> None:
    logger.remove()
    logger.add(sys.stdout, level="INFO", format="<level>{message}</level>")

    print(f"Fetching candles: {settings.SYMBOL}/{settings.TIMEFRAME}")
    raw = get_candles(settings.SYMBOL, settings.TIMEFRAME, limit=5000)
    if len(raw) < 200:
        print(f"ERROR: Only {len(raw)} candles in DB. Need ≥ 200. Run the bot first.")
        sys.exit(1)

    print(f"Computing indicators on {len(raw)} candles…")
    df = compute_indicators(raw)

    print("Generating labels…")
    df = generate_labels(df, forward_candles=4, threshold=0.003)
    if len(df) < 100:
        print(f"ERROR: Only {len(df)} labelled rows. Need more data.")
        sys.exit(1)

    print(f"Preparing features from {len(df)} rows…")
    X, y = prepare_features(df)
    print(f"Feature matrix: {X.shape}  |  Features: {FEATURE_COLS}")

    model = train_model(X, y)
    save_model(model)
    print(f"Model ready → {settings.MODEL_PATH}")


if __name__ == "__main__":
    main()
