import PnLChart from '@/components/PnLChart'
import type { DailyStat, PnLSummary } from '@/lib/types'
import { TrendingUp, TrendingDown, BarChart2, Calendar, Target, Zap } from 'lucide-react'

async function fetchPnLData(): Promise<{ stats: DailyStat[]; summary: PnLSummary }> {
  const base = process.env.NEXT_PUBLIC_BASE_URL ?? 'http://localhost:3000'
  const empty: PnLSummary = {
    total_signals: 0, buy_signals: 0, sell_signals: 0,
    avg_win_rate: 0, total_pnl_pct: 0, days_tracked: 0,
  }
  try {
    const [statsRes, summaryRes] = await Promise.all([
      fetch(`${base}/api/pnl?days=30`, { cache: 'no-store' }),
      fetch(`${base}/api/pnl/summary`, { cache: 'no-store' }),
    ])
    const stats: DailyStat[] = statsRes.ok ? await statsRes.json() : []
    const summary: PnLSummary = summaryRes.ok ? await summaryRes.json() : empty
    return { stats, summary }
  } catch {
    return { stats: [], summary: empty }
  }
}

interface StatCardProps {
  icon: React.ReactNode
  label: string
  value: string
  sub?: string
  accent?: 'green' | 'red' | 'teal' | 'default'
}

function StatCard({ icon, label, value, sub, accent = 'default' }: StatCardProps) {
  const accentClass = {
    green:   'text-emerald-400',
    red:     'text-red-400',
    teal:    'text-teal-400',
    default: 'text-gray-100',
  }[accent]

  return (
    <div className="bg-gray-900 rounded-2xl border border-gray-800 p-5 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">{label}</span>
        <span className="text-gray-700">{icon}</span>
      </div>
      <div>
        <p className={`text-3xl font-bold tracking-tight ${accentClass}`}>{value}</p>
        {sub && <p className="text-xs text-gray-500 mt-1">{sub}</p>}
      </div>
    </div>
  )
}

export default async function PnLPage() {
  const { stats, summary } = await fetchPnLData()

  const pnlPositive = summary.total_pnl_pct >= 0
  const pnlStr = `${pnlPositive ? '+' : ''}${(summary.total_pnl_pct * 100).toFixed(2)}%`
  const winRateStr = `${(summary.avg_win_rate * 100).toFixed(0)}%`

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-100">Performance</h1>
        <p className="text-sm text-gray-500 mt-1">Last 30 days · estimated from candle TP/SL touches</p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          icon={<Zap size={16} />}
          label="Total signals"
          value={String(summary.total_signals)}
          sub={`${summary.buy_signals} BUY · ${summary.sell_signals} SELL`}
        />
        <StatCard
          icon={<Target size={16} />}
          label="Win rate"
          value={winRateStr}
          sub={summary.days_tracked > 0 ? `over ${summary.days_tracked} days` : 'no data yet'}
          accent={summary.avg_win_rate >= 0.5 ? 'green' : summary.avg_win_rate > 0 ? 'teal' : 'default'}
        />
        <StatCard
          icon={pnlPositive ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
          label="Cumulative PnL"
          value={pnlStr}
          sub="account-level estimate"
          accent={pnlPositive ? 'green' : 'red'}
        />
        <StatCard
          icon={<Calendar size={16} />}
          label="Days tracked"
          value={String(summary.days_tracked)}
          sub="calendar days with signals"
        />
      </div>

      {/* Chart */}
      <div className="bg-gray-900 rounded-2xl border border-gray-800 p-5">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h2 className="text-sm font-semibold text-gray-200">Daily PnL</h2>
            <p className="text-xs text-gray-500 mt-0.5">Percentage of account per day</p>
          </div>
          <span className="flex items-center gap-1.5 text-xs text-gray-500 bg-gray-800 px-2.5 py-1 rounded-full">
            <BarChart2 size={11} />
            30d
          </span>
        </div>
        <PnLChart data={stats} />
      </div>
    </div>
  )
}
