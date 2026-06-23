PRAGMA journal_mode=WAL;

-- ─────────────────────────────────────────────
-- Raw OHLCV candle data
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS candles (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol    TEXT    NOT NULL,
    timeframe TEXT    NOT NULL,
    timestamp INTEGER NOT NULL,
    open      REAL    NOT NULL,
    high      REAL    NOT NULL,
    low       REAL    NOT NULL,
    close     REAL    NOT NULL,
    volume    REAL    NOT NULL,
    UNIQUE(symbol, timeframe, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_candles_ts
    ON candles(symbol, timeframe, timestamp DESC);

-- ─────────────────────────────────────────────
-- Generated trading signals
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS signals (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol       TEXT    NOT NULL,
    timestamp    INTEGER NOT NULL,
    direction    TEXT    NOT NULL CHECK(direction IN ('BUY','SELL','HOLD')),
    confidence   REAL    NOT NULL,
    entry_price  REAL    NOT NULL,
    stop_loss    REAL,
    take_profit  REAL,
    risk_reward  REAL,
    atr          REAL,
    published    INTEGER DEFAULT 0,
    created_at   TEXT    DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_signals_ts ON signals(timestamp DESC);

-- ─────────────────────────────────────────────
-- Executed trades (one row per open/closed position)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS trades (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id       INTEGER REFERENCES signals(id),
    symbol          TEXT    NOT NULL,
    direction       TEXT    NOT NULL CHECK(direction IN ('BUY','SELL')),
    status          TEXT    NOT NULL DEFAULT 'open'
                            CHECK(status IN ('open','closed','cancelled')),

    -- Entry fill
    entry_order_id  TEXT,
    entry_price     REAL    NOT NULL,
    quantity        REAL    NOT NULL,
    notional        REAL    NOT NULL,   -- entry_price * quantity (USDT value)
    fee_usdt        REAL    DEFAULT 0,

    -- Risk levels (stored so monitor can compare against live price)
    stop_loss       REAL    NOT NULL,
    take_profit     REAL    NOT NULL,

    -- Exit fill (populated on close)
    exit_order_id   TEXT,
    exit_price      REAL,
    exit_reason     TEXT    CHECK(exit_reason IN
                                ('take_profit','stop_loss','signal','manual',NULL)),
    pnl_usdt        REAL,
    pnl_pct         REAL,

    opened_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    closed_at       TEXT
);

CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol, status);

-- ─────────────────────────────────────────────
-- Daily performance summary
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS daily_stats (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    date             TEXT    NOT NULL UNIQUE,
    starting_balance REAL,
    ending_balance   REAL,
    total_signals    INTEGER DEFAULT 0,
    buy_signals      INTEGER DEFAULT 0,
    sell_signals     INTEGER DEFAULT 0,
    pnl_pct          REAL    DEFAULT 0,
    win_rate         REAL    DEFAULT 0,
    created_at       TEXT    DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_daily_stats_date ON daily_stats(date DESC);
