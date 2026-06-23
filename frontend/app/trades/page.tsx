'use client'
import useSWR from 'swr'
import { getTrades } from '@/lib/api'
import TradeCard from '@/components/TradeCard'
import type { Trade } from '@/lib/types'
import { RefreshCw, TrendingUp, DollarSign, Target } from 'lucide-react'

function StatPill({ label, value, color = 'text-gray-100' }: { label: string; value: string; color?: string }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl px-4 py-3">
      <p className="text-xs text-gray-500 mb-0.5">{label}</p>
      <p className={`text-xl font-bold ${color}`}>{value}</p>
    </div>
  )
}

export default function TradesPage() {
  const { data: trades = [], isLoading, isValidating } = useSWR<Trade[]>(
    'trades',
    () => getTrades(50),
    { refreshInterval: 15000 }
  )

  const open   = trades.filter(t => t.status === 'open')
  const closed = trades.filter(t => t.status === 'closed')
  const wins   = closed.filter(t => (t.pnl_usdt ?? 0) > 0)
  const totalPnl = closed.reduce((sum, t) => sum + (t.pnl_usdt ?? 0), 0)
  const winRate = closed.length > 0 ? wins.length / closed.length : 0

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Trades</h1>
          <p className="text-sm text-gray-500 mt-1">
            Live execution history · refreshes every 15s
          </p>
        </div>
        <RefreshCw
          size={14}
          className={`text-gray-500 ${isValidating ? 'animate-spin text-teal-400' : ''}`}
        />
      </div>

      {/* Summary stats */}
      {!isLoading && closed.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
          <StatPill label="Total trades"   value={String(closed.length)} />
          <StatPill
            label="Win rate"
            value={`${(winRate * 100).toFixed(0)}%`}
            color={winRate >= 0.5 ? 'text-emerald-400' : 'text-red-400'}
          />
          <StatPill
            label="Realized PnL"
            value={`${totalPnl >= 0 ? '+' : ''}${totalPnl.toFixed(2)} USDT`}
            color={totalPnl >= 0 ? 'text-emerald-400' : 'text-red-400'}
          />
          <StatPill label="Wins / Losses"  value={`${wins.length} / ${closed.length - wins.length}`} />
        </div>
      )}

      {isLoading && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {[1,2,3].map(i => (
            <div key={i} className="h-52 bg-gray-900 rounded-2xl border border-gray-800 animate-pulse" />
          ))}
        </div>
      )}

      {!isLoading && trades.length === 0 && (
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <div className="w-12 h-12 rounded-full bg-gray-800 flex items-center justify-center mb-4">
            <DollarSign size={20} className="text-gray-600" />
          </div>
          <p className="text-gray-400 font-medium">No trades yet</p>
          <p className="text-gray-600 text-sm mt-1">
            The bot will execute trades here when a signal fires above the confidence threshold.
          </p>
        </div>
      )}

      {!isLoading && open.length > 0 && (
        <div className="mb-8">
          <h2 className="text-sm font-semibold text-teal-400 uppercase tracking-wider mb-3 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-teal-400 animate-pulse inline-block" />
            Open position
          </h2>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {open.map(t => <TradeCard key={t.id} trade={t} />)}
          </div>
        </div>
      )}

      {!isLoading && closed.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">
            Trade history
          </h2>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {closed.map(t => <TradeCard key={t.id} trade={t} />)}
          </div>
        </div>
      )}
    </div>
  )
}
