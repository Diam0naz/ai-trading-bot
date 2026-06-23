import { format } from 'date-fns'
import type { Signal } from '@/lib/types'
import { TrendingUp, TrendingDown } from 'lucide-react'

interface Props { signal: Signal }

export default function SignalCard({ signal }: Props) {
  const isBuy = signal.direction === 'BUY'
  const { entry_price: entry, stop_loss: sl, take_profit: tp, risk_reward: rr } = signal

  const pct    = (val: number) => ((val - entry) / entry * 100)
  const fmtUSD = (n: number)   => n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  const dateStr = format(new Date(signal.timestamp), 'd MMM · HH:mm')
  const confPct = Math.round(signal.confidence * 100)

  return (
    <div className={`
      relative bg-gray-900 rounded-2xl border overflow-hidden
      transition-all duration-200 hover:shadow-lg hover:-translate-y-0.5
      ${isBuy ? 'border-emerald-500/30 hover:border-emerald-500/60' : 'border-red-500/30 hover:border-red-500/60'}
    `}>
      {/* Coloured top bar */}
      <div className={`h-0.5 w-full ${isBuy ? 'bg-gradient-to-r from-emerald-500 to-teal-400' : 'bg-gradient-to-r from-red-500 to-orange-400'}`} />

      <div className="p-4">
        {/* Header */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className={`
              inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold tracking-wide
              ${isBuy ? 'bg-emerald-500/15 text-emerald-400' : 'bg-red-500/15 text-red-400'}
            `}>
              {isBuy ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
              {signal.direction}
            </span>
            <span className="text-xs text-gray-500">{signal.symbol}</span>
          </div>
          <span className="text-xs text-gray-600">{dateStr}</span>
        </div>

        {/* Confidence bar */}
        <div className="mb-4">
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="text-gray-500">Model confidence</span>
            <span className={`font-semibold ${confPct >= 75 ? 'text-emerald-400' : confPct >= 65 ? 'text-teal-400' : 'text-amber-400'}`}>
              {confPct}%
            </span>
          </div>
          <div className="h-1.5 rounded-full bg-gray-800">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                confPct >= 75 ? 'bg-emerald-400' : confPct >= 65 ? 'bg-teal-400' : 'bg-amber-400'
              }`}
              style={{ width: `${confPct}%` }}
            />
          </div>
        </div>

        {/* Price levels */}
        <div className="space-y-2 text-sm">
          <div className="flex justify-between items-center py-1.5 border-b border-gray-800">
            <span className="text-gray-400">Entry</span>
            <span className="text-gray-100 font-mono font-semibold">${fmtUSD(entry)}</span>
          </div>

          {sl !== null && (
            <div className="flex justify-between items-center">
              <span className="text-gray-400">Stop loss</span>
              <div className="text-right">
                <span className="font-mono text-gray-300">${fmtUSD(sl)}</span>
                <span className="text-red-400 text-xs ml-1.5">
                  ({pct(sl) >= 0 ? '+' : ''}{pct(sl).toFixed(1)}%)
                </span>
              </div>
            </div>
          )}

          {tp !== null && (
            <div className="flex justify-between items-center">
              <span className="text-gray-400">Take profit</span>
              <div className="text-right">
                <span className="font-mono text-gray-300">${fmtUSD(tp)}</span>
                <span className="text-emerald-400 text-xs ml-1.5">
                  ({pct(tp) >= 0 ? '+' : ''}{pct(tp).toFixed(1)}%)
                </span>
              </div>
            </div>
          )}

          {rr !== null && (
            <div className="flex justify-between items-center pt-1.5 border-t border-gray-800">
              <span className="text-gray-500 text-xs">Risk / Reward</span>
              <span className={`text-xs font-semibold ${rr >= 1.5 ? 'text-emerald-400' : 'text-gray-400'}`}>
                1 : {rr.toFixed(1)}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
