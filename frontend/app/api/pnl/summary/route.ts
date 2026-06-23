import { NextResponse } from 'next/server'
import getDb from '@/lib/db'
import type { PnLSummary } from '@/lib/types'

interface StatRow {
  total_signals: number
  buy_signals: number
  sell_signals: number
  pnl_pct: number
  win_rate: number
}

export async function GET() {
  try {
    const db = getDb()
    const rows = db
      .prepare('SELECT * FROM daily_stats ORDER BY date DESC LIMIT 30')
      .all() as StatRow[]

    if (rows.length === 0) {
      return NextResponse.json<PnLSummary>({
        total_signals: 0,
        buy_signals: 0,
        sell_signals: 0,
        avg_win_rate: 0,
        total_pnl_pct: 0,
        days_tracked: 0,
      })
    }

    const nonZero = rows.filter((r) => r.win_rate > 0)
    const summary: PnLSummary = {
      total_signals: rows.reduce((a, r) => a + (r.total_signals ?? 0), 0),
      buy_signals: rows.reduce((a, r) => a + (r.buy_signals ?? 0), 0),
      sell_signals: rows.reduce((a, r) => a + (r.sell_signals ?? 0), 0),
      avg_win_rate:
        nonZero.length > 0
          ? nonZero.reduce((a, r) => a + r.win_rate, 0) / nonZero.length
          : 0,
      total_pnl_pct: rows.reduce((a, r) => a + (r.pnl_pct ?? 0), 0),
      days_tracked: rows.length,
    }

    return NextResponse.json(summary)
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 })
  }
}
