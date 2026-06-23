import { NextRequest, NextResponse } from 'next/server'
import getDb from '@/lib/db'

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url)
    const symbol = searchParams.get('symbol') ?? 'BTC/USDT'
    const timeframe = searchParams.get('timeframe') ?? '4h'
    const limit = Math.min(parseInt(searchParams.get('limit') ?? '200', 10), 500)

    const db = getDb()
    const rows = db
      .prepare(
        'SELECT timestamp, open, high, low, close, volume FROM candles WHERE symbol = ? AND timeframe = ? ORDER BY timestamp ASC LIMIT ?'
      )
      .all(symbol, timeframe, limit)

    return NextResponse.json(rows)
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 })
  }
}
