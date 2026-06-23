import { NextResponse } from 'next/server'
import getDb from '@/lib/db'
import type { BotStatus, OpenPosition } from '@/lib/types'

interface SignalRow {
  timestamp: number
  direction: string
  created_at: string
}

interface CountRow {
  cnt: number
}

interface PnlRow {
  pnl_pct: number
}

interface TradeRow {
  direction: string
  entry_price: number
  quantity: number
  stop_loss: number
  take_profit: number
  opened_at: string
}

export async function GET() {
  try {
    const db = getDb()

    // Last signal
    const lastSignal = db
      .prepare('SELECT timestamp, direction, created_at FROM signals ORDER BY timestamp DESC LIMIT 1')
      .get() as SignalRow | undefined

    let status: BotStatus['status'] = 'unknown'
    if (lastSignal) {
      const minutesSince = (Date.now() - lastSignal.timestamp) / 60000
      status = minutesSince < 30 ? 'running' : 'stalled'
    }

    // Signals today
    const today = new Date().toISOString().slice(0, 10)
    const { cnt: totalToday } = db
      .prepare("SELECT COUNT(*) as cnt FROM signals WHERE date(created_at) = ?")
      .get(today) as CountRow

    // Circuit breaker
    const todayStats = db
      .prepare('SELECT pnl_pct FROM daily_stats WHERE date = ?')
      .get(today) as PnlRow | undefined
    const maxLoss = parseFloat(process.env.MAX_DAILY_LOSS_PCT ?? '0.05')
    const circuitBreaker = todayStats ? todayStats.pnl_pct < -maxLoss : false

    // Open position
    const openTrade = db
      .prepare(`
        SELECT direction, entry_price, quantity, stop_loss, take_profit, opened_at
        FROM trades WHERE status = 'open'
        ORDER BY opened_at DESC LIMIT 1
      `)
      .get() as TradeRow | undefined

    const open_position: OpenPosition | null = openTrade
      ? {
          direction:   openTrade.direction as 'BUY' | 'SELL',
          entry_price: openTrade.entry_price,
          quantity:    openTrade.quantity,
          stop_loss:   openTrade.stop_loss,
          take_profit: openTrade.take_profit,
          opened_at:   openTrade.opened_at,
        }
      : null

    const result: BotStatus = {
      status,
      last_signal_at:         lastSignal?.created_at ?? null,
      last_signal_direction:  lastSignal?.direction ?? null,
      total_signals_today:    totalToday,
      circuit_breaker_active: circuitBreaker,
      testnet:                process.env.BOT_TESTNET === 'true',
      symbol:                 process.env.BOT_SYMBOL ?? 'BTC/USDT',
      timeframe:              process.env.BOT_TIMEFRAME ?? '4h',
      open_position,
    }

    return NextResponse.json(result)
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 })
  }
}
