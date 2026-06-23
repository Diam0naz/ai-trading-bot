# TradingBot

AI-powered crypto trading bot with a Next.js dashboard. Fetches live market data from **CoinGecko**, generates BUY/SELL signals using an XGBoost model trained on technical indicators, executes market orders on **Binance**, and displays everything on a real-time web dashboard.

---

## Architecture

```
┌─────────────────────────────────┐     ┌──────────────────────────────┐
│         Python Bot              │     │       Next.js Dashboard      │
│                                 │     │                              │
│  CoinGecko → Candles → Model    │     │  /          Signal feed      │
│  → Signal → Execute on Binance ─┼──▶  │  /trades    Trade history   │
│  → Monitor SL/TP               │     │  /pnl       Performance      │
│  → Telegram alerts         SQLite     │  /chart     Candlestick      │
│                            (WAL) ◀────┤  /status    Bot health       │
└─────────────────────────────────┘     └──────────────────────────────┘
```

**Data vs. execution are split:**
- **CoinGecko** provides all OHLCV market data (free, no exchange account needed).
- **Binance** is used only to place and close orders — CoinGecko cannot trade.

The Python bot is the **sole writer** to SQLite. Next.js reads from it (read-only). Telegram receives trade alerts. No shared server process between the two layers.

> **Timeframe note:** CoinGecko fixes candle granularity by the lookback window, so the supported `TIMEFRAME` values are `30m`, `4h`, and `4d`. **`4h` is the default and recommended** — it gives ~180 candles, enough history for the 50-period indicators. (`30m` only returns ~48 candles, too few for warm-up.)

---

## Prerequisites

- Python 3.12+
- Node.js 18+
- SQLite3 (usually pre-installed)
- A Binance account (testnet or live)
- A Telegram bot + channel

---

## Quick start

### 1. Initialize the database

```bash
sqlite3 db/trading_bot.db < db/init_db.sql
```

### 2. Set up the Python bot

```bash
cd bot
python3.12 -m venv ../.venv
source ../.venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# → fill in your API keys (see below)
```

### 3. Train the model

The bot needs historical data before it can train. Run a quick seed fetch first:

```bash
cd ..   # project root
python - <<'EOF'
from bot.data.fetcher import fetch_ohlcv
from bot.data.storage import upsert_candles
from bot.config.settings import settings
# fetch_ohlcv already tags symbol + timeframe columns
df = fetch_ohlcv(settings.SYMBOL, settings.TIMEFRAME)
upsert_candles(df)
print(f"Stored {len(df)} candles")
EOF

python -m bot.model.trainer
```

Review the 5-fold validation output — if mean accuracy is below 0.55, collect more data before going live.

### 4. Run the bot

```bash
python -m bot.loop
```

You will receive a Telegram message when the bot starts. The first signal check runs immediately, then every 15 minutes.

### 5. Run the dashboard

```bash
cd frontend
cp .env.local.example .env.local
# → set DATABASE_PATH to the absolute path of db/trading_bot.db

npm install
npm run dev
# → open http://localhost:3000
```

---

## Getting your API keys

### CoinGecko (market data)

No key is required for the free tier (~30 requests/min) — leave `COINGECKO_API_KEY` blank. The bot fetches candles only once per cycle, so the free tier is plenty. For higher limits, create a free **Demo API key** at [coingecko.com/en/api](https://www.coingecko.com/en/api) and paste it into `COINGECKO_API_KEY`.

### Binance testnet (safe, fake money)

1. Visit [testnet.binance.vision](https://testnet.binance.vision) and log in with GitHub
2. Click **Generate HMAC_SHA256 Key**
3. Copy the API Key and Secret Key into `bot/.env`
4. Leave `BINANCE_TESTNET=true`

### Binance live (real money — be careful)

1. Log in to [binance.com](https://www.binance.com) → API Management
2. Create a new API key with **Spot trading** enabled
3. Restrict by IP address for safety
4. Set `BINANCE_TESTNET=false` in `bot/.env`

### Telegram bot setup

1. Message `@BotFather` → `/newbot` → follow prompts → copy the token
2. Add the bot as an admin to your channel
3. Public channel: use `@your_channel_name` as `TELEGRAM_CHANNEL_ID`
4. Private channel: forward a message to `@userinfobot` to get the numeric ID

---

## Keep it running

```bash
# In a tmux session so it survives SSH disconnect
tmux new -s bot
source .venv/bin/activate
python -m bot.loop

# Detach: Ctrl+B then D
# Reattach: tmux attach -t bot
```

---

## How trading works

Every 15 minutes the bot does one of two things:

**If a position is open:**
- Fetches live price from Binance
- Checks if stop-loss or take-profit has been reached
- Also checks if the model now gives a SELL signal (early exit)
- Closes position with a market sell if any condition is met
- Sends Telegram alert with realized PnL

**If no position is open:**
- Fetches latest candles, stores them
- Runs XGBoost model on the last 500 candles
- If confidence ≥ threshold and direction = BUY: places a market buy order
- SELL signals on spot = no execution (can't short on spot)

---

## Configuration reference (`bot/.env`)

| Variable | Default | Description |
|---|---|---|
| `COINGECKO_API_KEY` | _(blank)_ | Optional CoinGecko Demo key; blank = free tier |
| `BINANCE_API_KEY` | — | API key from Binance (execution only) |
| `BINANCE_SECRET` | — | Secret key from Binance |
| `BINANCE_TESTNET` | `true` | Use testnet (fake money) |
| `DATABASE_PATH` | `db/trading_bot.db` | Path to SQLite file |
| `TELEGRAM_BOT_TOKEN` | — | Token from BotFather |
| `TELEGRAM_CHANNEL_ID` | — | Channel username or numeric ID |
| `SYMBOL` | `BTC/USDT` | Trading pair (base mapped to a CoinGecko coin id) |
| `TIMEFRAME` | `4h` | Candle interval — `30m`, `4h`, or `4d` |
| `SIGNAL_THRESHOLD` | `0.65` | Min model confidence to act (0–1) |
| `MAX_DAILY_LOSS_PCT` | `0.05` | Circuit breaker threshold (5%) |
| `POSITION_SIZE_PCT` | `0.02` | Capital per trade (2% of balance) |
| `ATR_MULTIPLIER_SL` | `1.5` | Stop loss = ATR × 1.5 |
| `ATR_MULTIPLIER_TP` | `2.5` | Take profit = ATR × 2.5 |
| `MODEL_PATH` | `bot/model/xgb_signal_model.joblib` | Model file location |
| `LOG_PATH` | `logs/bot.log` | Log file location |

---

## Retraining the model

After the bot has been running for several days, retrain with fresh data:

```bash
python -m bot.model.trainer
```

Or use Cell 5 in `notebooks/analysis.ipynb`. Review the validation metrics before restarting the bot.

---

## Disclaimer

This bot is for educational purposes. Not financial advice. Always test on testnet before using real funds. Never risk money you cannot afford to lose. Past signal accuracy does not guarantee future performance.
