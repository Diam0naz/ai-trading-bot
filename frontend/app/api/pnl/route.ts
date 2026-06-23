import { NextRequest, NextResponse } from 'next/server'
import getDb from '@/lib/db'

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url)
    const days = parseInt(searchParams.get('days') ?? '30', 10)

    const db = getDb()
    const rows = db
      .prepare('SELECT * FROM daily_stats ORDER BY date DESC LIMIT ?')
      .all(days) as Array<Record<string, unknown>>

    return NextResponse.json(rows.reverse())
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 })
  }
}
