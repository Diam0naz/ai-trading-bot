"""Order execution via ccxt Binance.

Handles market orders, balance queries, and price fetching.
All functions work identically on testnet and live — the exchange
instance controls which endpoint is used.

Supported flow (spot only):
  BUY signal  → place market BUY → store open trade
  Price hits SL/TP → place market SELL → store closed trade
  SELL signal with no open position → skipped (no shorting on spot)
"""

from __future__ import annotations

import time
from typing import Optional

import ccxt
from loguru import logger

from bot.config.settings import settings

_exchange: Optional[ccxt.binance] = None


def _get_exchange() -> ccxt.binance:
    """Return a cached Binance exchange configured for execution."""
    global _exchange
    if _exchange is None:
        opts: dict = {
            "apiKey": settings.BINANCE_API_KEY,
            "secret": settings.BINANCE_SECRET,
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        }
        _exchange = ccxt.binance(opts)
        if settings.BINANCE_TESTNET:
            _exchange.set_sandbox_mode(True)
            logger.info("Trader initialised [TESTNET]")
        else:
            logger.warning("Trader initialised [LIVE] — real funds at risk!")
    return _exchange


# ─────────────────────────────────────────────
# Account info
# ─────────────────────────────────────────────


def get_free_balance(asset: str = "USDT") -> float:
    """Return the free (available) balance for the given asset.

    Args:
        asset: Quote currency symbol, e.g. "USDT".

    Returns:
        Available balance as a float.
    """
    balance = _get_exchange().fetch_balance()
    free = float(balance.get(asset, {}).get("free", 0.0))
    logger.debug("Free balance: {:.2f} {}", free, asset)
    return free


def get_current_price(symbol: Optional[str] = None) -> float:
    """Fetch the latest trade price for a symbol.

    Args:
        symbol: Trading pair (defaults to settings.SYMBOL).

    Returns:
        Latest price as a float.
    """
    symbol = symbol or settings.SYMBOL
    ticker = _get_exchange().fetch_ticker(symbol)
    price = float(ticker["last"])
    logger.debug("Current price {}: {:.2f}", symbol, price)
    return price


# ─────────────────────────────────────────────
# Order execution
# ─────────────────────────────────────────────


def place_market_order(symbol: str, side: str, quantity: float) -> dict:
    """Place a market order and return fill details.

    Rounds quantity to exchange precision before sending.
    Retries order fetch once if fill price is missing (testnet quirk).

    Args:
        symbol:   Trading pair, e.g. "BTC/USDT".
        side:     "buy" or "sell".
        quantity: Base asset quantity to trade.

    Returns:
        Dict with: order_id, side, quantity, avg_price, cost, fee_usdt.

    Raises:
        ccxt.BaseError: On any exchange error.
    """
    exchange = _get_exchange()

    # Round to exchange-mandated lot size
    qty_precise = float(exchange.amount_to_precision(symbol, quantity))
    if qty_precise <= 0:
        raise ValueError(f"Quantity {quantity} rounds to zero for {symbol} — check position size settings")

    logger.info("Placing market {} {} {}", side.upper(), qty_precise, symbol)

    order = exchange.create_order(
        symbol=symbol,
        type="market",
        side=side,
        amount=qty_precise,
    )

    # Testnet sometimes returns unfilled order immediately — wait and refetch
    if not order.get("average") and not order.get("price"):
        time.sleep(1.5)
        order = exchange.fetch_order(order["id"], symbol)

    avg_price = float(order.get("average") or order.get("price") or 0)
    filled_qty = float(order.get("filled") or qty_precise)
    cost = float(order.get("cost") or avg_price * filled_qty)
    fee = order.get("fee") or {}
    fee_usdt = float(fee.get("cost", 0.0)) if isinstance(fee, dict) else 0.0

    logger.info(
        "Order filled: {} {} {} @ {:.4f}  cost={:.2f} USDT  fee={:.4f}",
        side.upper(), filled_qty, symbol, avg_price, cost, fee_usdt,
    )

    return {
        "order_id": str(order["id"]),
        "side": side,
        "quantity": filled_qty,
        "avg_price": avg_price,
        "cost": cost,
        "fee_usdt": fee_usdt,
    }


def close_position(symbol: str, quantity: float) -> dict:
    """Close a long position by placing a market sell.

    Args:
        symbol:   Trading pair.
        quantity: Exact quantity to sell (from the open trade record).

    Returns:
        Fill details dict (same shape as place_market_order).
    """
    return place_market_order(symbol, "sell", quantity)
