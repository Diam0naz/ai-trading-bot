import { NextRequest, NextResponse } from 'next/server'
import getDb from '@/lib/db'

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url)
    const limit = Math.min(parseInt(searchParams.get('limit') ?? '20', 10), 100)
    const symbol = searchParams.get('symbol')

    const db = getDb()
    const rows = symbol
      ? db.prepare('SELECT * FROM signals WHERE symbol = ? ORDER BY timestamp DESC LIMIT ?').all(symbol, limit)
      : db.prepare('SELECT * FROM signals ORDER BY timestamp DESC LIMIT ?').all(limit)

    return NextResponse.json(rows)
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 })
  }
}
