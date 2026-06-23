'use client'
import type { Trade } from '@/lib/types'
import { format, formatDistanceToNow } from 'date-fns'
import { TrendingUp, TrendingDown, Clock, CheckCircle, XCircle } from 'lucide-react'

interface Props { trade: Trade }

const REASON_LABEL: Record<string, string> = {
  take_profit: 'Take profit hit',
  stop_loss:   'Stop loss hit',
  signal:      'Closed by signal',
  manual:      'Manually closed',
}

export default function TradeCard({ trade }: Props) {
  const isOpen  = trade.status === 'open'
  const isWin   = (trade.pnl_usdt ?? 0) > 0
  const isBuy   = trade.direction === 'BUY'

  const fmtUSD = (n: number) =>
    n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

  const openedAt = format(new Date(trade.opened_at), 'd MMM HH:mm')
  const openedAgo = formatDistanceToNow(new Date(trade.opened_at), { addSuffix: true })

  return (
    <div className={`
      bg-gray-900 rounded-2xl border overflow-hidden
      ${isOpen
        ? 'border-teal-500/40 shadow-teal-500/5 shadow-lg'
        : isWin ? 'border-emerald-500/20' : 'border-red-500/20'
      }
    `}>
      {/* Status bar */}
      <div className={`h-0.5 w-full ${
        isOpen ? 'bg-teal-400' : isWin ? 'bg-emerald-500' : 'bg-red-500'
      }`} />

      <div className="p-4">
        {/* Header */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className={`
              inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold
              ${isBuy ? 'bg-emerald-500/15 text-emerald-400' : 'bg-red-500/15 text-red-400'}
            `}>
              {isBuy ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
              {trade.direction}
            </span>
            <span className="text-xs text-gray-500">{trade.symbol}</span>
          </div>

          {/* Status badge */}
          {isOpen ? (
            <span className="flex items-center gap-1 text-xs text-teal-400 font-medium animate-pulse">
              <Clock size={11} />
              Open
            </span>
          ) : (
            <span className={`flex items-center gap-1 text-xs font-medium ${isWin ? 'text-emerald-400' : 'text-red-400'}`}>
              {isWin ? <CheckCircle size={11} /> : <XCircle size={11} />}
              {trade.exit_reason ? REASON_LABEL[trade.exit_reason] ?? trade.exit_reason : 'Closed'}
            </span>
          )}
        </div>

        {/* Price grid */}
        <div className="space-y-1.5 text-sm mb-3">
          <div className="flex justify-between">
            <span className="text-gray-400">Entry</span>
            <span className="font-mono text-gray-100">${fmtUSD(trade.entry_price)}</span>
          </div>

          {isOpen ? (
            <>
              <div className="flex justify-between">
                <span className="text-gray-400">Stop loss</span>
                <span className="font-mono text-red-400">${fmtUSD(trade.stop_loss)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Take profit</span>
                <span className="font-mono text-emerald-400">${fmtUSD(trade.take_profit)}</span>
              </div>
            </>
          ) : trade.exit_price !== null ? (
            <div className="flex justify-between">
              <span className="text-gray-400">Exit</span>
              <span className="font-mono text-gray-100">${fmtUSD(trade.exit_price)}</span>
            </div>
          ) : null}
        </div>

        {/* PnL — only for closed trades */}
        {!isOpen && trade.pnl_usdt !== null && (
          <div className={`
            rounded-xl px-3 py-2 flex items-center justify-between text-sm font-semibold mb-3
            ${isWin ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}
          `}>
            <span>Realized PnL</span>
            <span>
              {trade.pnl_usdt >= 0 ? '+' : ''}{fmtUSD(trade.pnl_usdt)} USDT
              {trade.pnl_pct !== null && (
                <span className="text-xs ml-1.5 opacity-70">
                  ({trade.pnl_pct >= 0 ? '+' : ''}{(trade.pnl_pct * 100).toFixed(2)}%)
                </span>
              )}
            </span>
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between text-xs text-gray-600 pt-2 border-t border-gray-800">
          <span>Qty: {trade.quantity.toFixed(6)}</span>
          <span title={openedAt}>{openedAgo}</span>
        </div>
      </div>
    </div>
  )
}
