"""Central configuration — loads all secrets from .env and exposes a typed Settings object."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent.parent  # project root (trading_bot/)
load_dotenv(_ROOT / "bot" / ".env")


def _required(key: str) -> str:
    v = os.getenv(key)
    if not v:
        raise EnvironmentError(f"Required env var '{key}' is not set. Check bot/.env")
    return v


def _bool(key: str, default: bool = False) -> bool:
    return os.getenv(key, str(default)).lower() in ("1", "true", "yes")


def _float(key: str, default: float) -> float:
    return float(os.getenv(key, str(default)))


def _path(key: str, default: str) -> str:
    raw = os.getenv(key, default)
    return str(Path(raw).resolve())


@dataclass(frozen=True)
class Settings:
    # ── CoinGecko (market data) ───────────────────────────────────────────
    COINGECKO_API_KEY: str          # empty string = free tier (30 req/min)

    # ── Binance (order execution only) ───────────────────────────────────
    BINANCE_API_KEY: str
    BINANCE_SECRET: str
    BINANCE_TESTNET: bool

    # ── Database ──────────────────────────────────────────────────────────
    DATABASE_PATH: str

    # ── Telegram ──────────────────────────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_CHANNEL_ID: str

    # ── Trading pair / timeframe ──────────────────────────────────────────
    SYMBOL: str
    TIMEFRAME: str                  # '4h' recommended for CoinGecko free tier

    # ── Signal quality gate ───────────────────────────────────────────────
    SIGNAL_THRESHOLD: float

    # ── Risk management ───────────────────────────────────────────────────
    MAX_DAILY_LOSS_PCT: float
    POSITION_SIZE_PCT: float
    ATR_MULTIPLIER_SL: float
    ATR_MULTIPLIER_TP: float

    # ── Paths ─────────────────────────────────────────────────────────────
    MODEL_PATH: str
    LOG_PATH: str


def _load() -> Settings:
    return Settings(
        COINGECKO_API_KEY=os.getenv("COINGECKO_API_KEY", ""),
        BINANCE_API_KEY=_required("BINANCE_API_KEY"),
        BINANCE_SECRET=_required("BINANCE_SECRET"),
        BINANCE_TESTNET=_bool("BINANCE_TESTNET", default=True),
        DATABASE_PATH=_path("DATABASE_PATH", "db/trading_bot.db"),
        TELEGRAM_BOT_TOKEN=_required("TELEGRAM_BOT_TOKEN"),
        TELEGRAM_CHANNEL_ID=_required("TELEGRAM_CHANNEL_ID"),
        SYMBOL=os.getenv("SYMBOL", "BTC/USDT"),
        TIMEFRAME=os.getenv("TIMEFRAME", "4h"),
        SIGNAL_THRESHOLD=_float("SIGNAL_THRESHOLD", 0.65),
        MAX_DAILY_LOSS_PCT=_float("MAX_DAILY_LOSS_PCT", 0.05),
        POSITION_SIZE_PCT=_float("POSITION_SIZE_PCT", 0.02),
        ATR_MULTIPLIER_SL=_float("ATR_MULTIPLIER_SL", 1.5),
        ATR_MULTIPLIER_TP=_float("ATR_MULTIPLIER_TP", 2.5),
        MODEL_PATH=_path("MODEL_PATH", "bot/model/xgb_signal_model.joblib"),
        LOG_PATH=_path("LOG_PATH", "logs/bot.log"),
    )


settings = _load()
