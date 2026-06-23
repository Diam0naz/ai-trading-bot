"""OHLCV market data from the CoinGecko API.

CoinGecko is the data source (free, no exchange account needed). Binance is used
only for order execution in bot/execution/trader.py — CoinGecko cannot place trades.

CoinGecko OHLC granularity is fixed by the `days` window (free tier):
    days = 1        → 30-minute candles  (~48 rows)
    days = 2..30    → 4-hour candles     (~180 rows at days=30)
    days = 31..     → 4-day candles

So the supported TIMEFRAME values map to:
    "30m" → days=1
    "4h"  → days=30   (recommended default)
    "4d"  → days=365

The OHLC endpoint carries no volume, so volume is fetched separately from
/market_chart (24h rolling volume) and merged onto each candle by nearest
timestamp. Volume is therefore a proxy, which is fine for the volume-ratio feature.
"""

from __future__ import annotations

import time
from typing import Optional

import pandas as pd
import requests
from loguru import logger

from bot.config.settings import settings

_BASE_URL = "https://api.coingecko.com/api/v3"
_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]

# Map a base asset symbol to its CoinGecko coin id.
_COIN_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "BNB": "binancecoin",
    "SOL": "solana",
    "XRP": "ripple",
    "ADA": "cardano",
    "DOGE": "dogecoin",
    "AVAX": "avalanche-2",
    "DOT": "polkadot",
    "MATIC": "matic-network",
    "LINK": "chainlink",
    "LTC": "litecoin",
}

# Map a TIMEFRAME string to the CoinGecko `days` window that yields it.
_TIMEFRAME_DAYS = {
    "30m": 1,
    "4h": 30,
    "4d": 365,
}


def _parse_symbol(symbol: str) -> tuple[str, str]:
    """Split 'BTC/USDT' into a CoinGecko coin id and vs_currency.

    Args:
        symbol: Trading pair such as 'BTC/USDT'.

    Returns:
        (coin_id, vs_currency), e.g. ('bitcoin', 'usd').

    Raises:
        ValueError: If the base asset has no known CoinGecko id.
    """
    base = symbol.split("/")[0].upper()
    coin_id = _COIN_IDS.get(base)
    if coin_id is None:
        raise ValueError(
            f"No CoinGecko coin id mapped for '{base}'. "
            f"Add it to _COIN_IDS in bot/data/fetcher.py. Known: {sorted(_COIN_IDS)}"
        )
    # USDT / USDC / BUSD all track USD on CoinGecko
    return coin_id, "usd"


def _days_for_timeframe(timeframe: str) -> int:
    """Return the CoinGecko `days` window for a timeframe string."""
    days = _TIMEFRAME_DAYS.get(timeframe)
    if days is None:
        raise ValueError(
            f"TIMEFRAME '{timeframe}' is not supported with CoinGecko. "
            f"Use one of: {sorted(_TIMEFRAME_DAYS)} (CoinGecko fixes granularity by window)."
        )
    return days


def _headers() -> dict:
    """Return request headers, including the demo API key if configured."""
    if settings.COINGECKO_API_KEY:
        return {"x-cg-demo-api-key": settings.COINGECKO_API_KEY}
    return {}


def _get_json(path: str, params: dict, attempts: int = 3, base_delay: float = 2.0):
    """GET a CoinGecko endpoint with exponential backoff on rate limits / errors.

    Args:
        path:       Endpoint path, e.g. '/coins/bitcoin/ohlc'.
        params:     Query parameters.
        attempts:   Maximum attempts before raising.
        base_delay: Base backoff delay (seconds), doubled each retry.

    Returns:
        Parsed JSON response.

    Raises:
        RuntimeError: If all attempts fail.
    """
    url = f"{_BASE_URL}{path}"
    for attempt in range(1, attempts + 1):
        try:
            resp = requests.get(url, params=params, headers=_headers(), timeout=20)
            if resp.status_code == 429:
                delay = base_delay * (2 ** (attempt - 1))
                logger.warning("CoinGecko rate limit (attempt {}/{}). Waiting {}s", attempt, attempts, delay)
                time.sleep(delay)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning("CoinGecko request error attempt {}/{}: {}. Waiting {}s", attempt, attempts, exc, delay)
            time.sleep(delay)
    raise RuntimeError(f"CoinGecko request to {path} failed after {attempts} attempts")


def _fetch_ohlc(coin_id: str, vs_currency: str, days: int) -> pd.DataFrame:
    """Fetch raw OHLC candles (no volume) from CoinGecko.

    Returns:
        DataFrame with columns [timestamp, open, high, low, close]; timestamp is Unix ms int.
    """
    raw = _get_json(
        f"/coins/{coin_id}/ohlc",
        {"vs_currency": vs_currency, "days": days},
    )
    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close"])
    df["timestamp"] = df["timestamp"].astype("int64")
    for col in ("open", "high", "low", "close"):
        df[col] = df[col].astype(float)
    return df.sort_values("timestamp").reset_index(drop=True)


def _fetch_volume(coin_id: str, vs_currency: str, days: int) -> pd.DataFrame:
    """Fetch the 24h rolling volume series from CoinGecko /market_chart.

    Returns:
        DataFrame with columns [timestamp, volume]; timestamp is Unix ms int.
        Empty DataFrame if the request fails (volume is non-critical).
    """
    try:
        raw = _get_json(
            f"/coins/{coin_id}/market_chart",
            {"vs_currency": vs_currency, "days": days},
        )
        vols = raw.get("total_volumes", [])
        df = pd.DataFrame(vols, columns=["timestamp", "volume"])
        df["timestamp"] = df["timestamp"].astype("int64")
        df["volume"] = df["volume"].astype(float)
        return df.sort_values("timestamp").reset_index(drop=True)
    except Exception as exc:
        logger.warning("Volume fetch failed ({}); proceeding without real volume", exc)
        return pd.DataFrame(columns=["timestamp", "volume"])


def _merge_volume(ohlc: pd.DataFrame, vol: pd.DataFrame) -> pd.DataFrame:
    """Attach the nearest volume reading to each OHLC candle via merge_asof.

    Args:
        ohlc: OHLC DataFrame (timestamp ascending).
        vol:  Volume DataFrame (timestamp ascending), may be empty.

    Returns:
        OHLC DataFrame with a 'volume' column (1.0 fallback where unavailable).
    """
    if vol.empty:
        ohlc = ohlc.copy()
        ohlc["volume"] = 1.0
        return ohlc

    merged = pd.merge_asof(
        ohlc.sort_values("timestamp"),
        vol.sort_values("timestamp"),
        on="timestamp",
        direction="nearest",
    )
    merged["volume"] = merged["volume"].fillna(1.0).astype(float)
    return merged


def fetch_ohlcv(
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
    limit: int = 500,
) -> pd.DataFrame:
    """Fetch OHLCV candles for a symbol from CoinGecko.

    Args:
        symbol:    Trading pair (defaults to settings.SYMBOL), e.g. 'BTC/USDT'.
        timeframe: '30m', '4h', or '4d' (defaults to settings.TIMEFRAME).
        limit:     Max candles to return (CoinGecko caps by the days window;
                   the most recent `limit` rows are returned).

    Returns:
        DataFrame with columns [symbol, timeframe, timestamp, open, high, low,
        close, volume]. timestamp is Unix milliseconds (integer).
    """
    symbol = symbol or settings.SYMBOL
    timeframe = timeframe or settings.TIMEFRAME

    coin_id, vs_currency = _parse_symbol(symbol)
    days = _days_for_timeframe(timeframe)

    ohlc = _fetch_ohlc(coin_id, vs_currency, days)
    vol = _fetch_volume(coin_id, vs_currency, days)
    df = _merge_volume(ohlc, vol)

    # Tag and trim to the requested limit (most recent rows)
    df.insert(0, "symbol", symbol)
    df.insert(1, "timeframe", timeframe)
    df = df[["symbol", "timeframe", *_COLUMNS]]
    if len(df) > limit:
        df = df.tail(limit).reset_index(drop=True)

    logger.info(
        "CoinGecko: fetched {} {} candles for {} (days={}) — latest ts={}",
        len(df), timeframe, symbol, days, df["timestamp"].iloc[-1] if len(df) else "—",
    )
    return df


def fetch_latest_candle(
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
) -> pd.DataFrame:
    """Fetch the single most-recent candle.

    Args:
        symbol:    Trading pair (defaults to settings.SYMBOL).
        timeframe: Candle interval (defaults to settings.TIMEFRAME).

    Returns:
        Single-row DataFrame.
    """
    df = fetch_ohlcv(symbol=symbol, timeframe=timeframe)
    return df.iloc[[-1]].reset_index(drop=True)
