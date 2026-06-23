export interface Signal {
  id: number
  symbol: string
  timestamp: number
  direction: 'BUY' | 'SELL' | 'HOLD'
  confidence: number
  entry_price: number
  stop_loss: number | null
  take_profit: number | null
  risk_reward: number | null
  atr: number | null
  published: number
  created_at: string
}

export interface Candle {
  timestamp: number
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface DailyStat {
  date: string
  total_signals: number
  buy_signals: number
  sell_signals: number
  pnl_pct: number
  win_rate: number
}

export interface PnLSummary {
  total_signals: number
  buy_signals: number
  sell_signals: number
  avg_win_rate: number
  total_pnl_pct: number
  days_tracked: number
}

export interface Trade {
  id: number
  signal_id: number | null
  symbol: string
  direction: 'BUY' | 'SELL'
  status: 'open' | 'closed' | 'cancelled'
  entry_order_id: string | null
  entry_price: number
  quantity: number
  notional: number
  fee_usdt: number
  stop_loss: number
  take_profit: number
  exit_order_id: string | null
  exit_price: number | null
  exit_reason: 'take_profit' | 'stop_loss' | 'signal' | 'manual' | null
  pnl_usdt: number | null
  pnl_pct: number | null
  opened_at: string
  closed_at: string | null
}

export interface OpenPosition {
  direction: 'BUY' | 'SELL'
  entry_price: number
  quantity: number
  stop_loss: number
  take_profit: number
  opened_at: string
}

export interface BotStatus {
  status: 'running' | 'stalled' | 'unknown'
  last_signal_at: string | null
  last_signal_direction: string | null
  total_signals_today: number
  circuit_breaker_active: boolean
  testnet: boolean
  symbol: string
  timeframe: string
  open_position: OpenPosition | null
}
