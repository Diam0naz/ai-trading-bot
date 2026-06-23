import { NextRequest, NextResponse } from 'next/server'
import getDb from '@/lib/db'

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url)
    const limit = Math.min(parseInt(searchParams.get('limit') ?? '50', 10), 200)

    const db = getDb()
    const rows = db.prepare(`
      SELECT * FROM trades
      ORDER BY
        CASE status WHEN 'open' THEN 0 ELSE 1 END ASC,
        opened_at DESC
      LIMIT ?
    `).all(limit)

    return NextResponse.json(rows)
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 })
  }
}
