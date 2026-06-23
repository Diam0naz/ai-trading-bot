'use client'
import { formatDistanceToNow, format } from 'date-fns'
import { CheckCircle, XCircle, Wifi, WifiOff, HelpCircle, Shield, TrendingUp } from 'lucide-react'
import type { BotStatus } from '@/lib/types'

interface Props { status: BotStatus }

const STATUS_CONFIG: Record<BotStatus['status'], {
  dot: string; dotClass: string; label: string; icon: React.ReactNode; bg: string
}> = {
  running: {
    dot: 'bg-emerald-400',
    dotClass: 'status-dot-running',
    label: 'Running',
    icon: <Wifi size={14} className="text-emerald-400" />,
    bg: 'bg-emerald-500/10 border-emerald-500/20',
  },
  stalled: {
    dot: 'bg-amber-400',
    dotClass: '',
    label: 'Stalled — no signal in 30+ min',
    icon: <WifiOff size={14} className="text-amber-400" />,
    bg: 'bg-amber-500/10 border-amber-500/20',
  },
  unknown: {
    dot: 'bg-gray-500',
    dotClass: '',
    label: 'Unknown — no signals yet',
    icon: <HelpCircle size={14} className="text-gray-500" />,
    bg: 'bg-gray-800/60 border-gray-700',
  },
}

export default function BotStatusCard({ status }: Props) {
  const cfg = STATUS_CONFIG[status.status]
  const pos = status.open_position

  const lastAt = status.last_signal_at
    ? formatDistanceToNow(new Date(status.last_signal_at), { addSuffix: true })
    : null

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">

      {/* Status banner — full width */}
      <div className={`sm:col-span-2 lg:col-span-3 rounded-2xl border p-4 ${cfg.bg} flex items-center justify-between`}>
        <div className="flex items-center gap-3">
          <span className={`w-3 h-3 rounded-full ${cfg.dot} ${cfg.dotClass} shadow-lg`} />
          <div className="flex items-center gap-2">
            {cfg.icon}
            <span className="font-semibold text-gray-100 text-sm">{cfg.label}</span>
          </div>
        </div>
        {status.testnet && (
          <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/20">
            TESTNET
          </span>
        )}
      </div>

      {/* Info cards */}
      <InfoCard label="Symbol"        value={status.symbol}              sub={status.timeframe} />
      <InfoCard
        label="Last signal"
        value={lastAt ?? 'Never'}
        sub={status.last_signal_direction ?? '—'}
        subColor={
          status.last_signal_direction === 'BUY'  ? 'text-emerald-400' :
          status.last_signal_direction === 'SELL' ? 'text-red-400'     : 'text-gray-500'
        }
      />
      <InfoCard label="Signals today" value={String(status.total_signals_today)} sub="generated so far" />

      {/* Open position — full width, only shown when in a trade */}
      {pos ? (
        <div className="sm:col-span-2 lg:col-span-3 bg-gray-900 rounded-2xl border border-teal-500/30 p-4">
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp size={14} className="text-teal-400" />
            <span className="text-sm font-semibold text-teal-400">Open position</span>
            <span className="ml-auto text-xs text-gray-500">
              Opened {formatDistanceToNow(new Date(pos.opened_at), { addSuffix: true })}
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
            <div>
              <p className="text-xs text-gray-500 mb-0.5">Direction</p>
              <p className={`font-bold ${pos.direction === 'BUY' ? 'text-emerald-400' : 'text-red-400'}`}>
                {pos.direction === 'BUY' ? '🟢 LONG' : '🔴 SHORT'}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-0.5">Entry price</p>
              <p className="font-mono font-semibold text-gray-100">${pos.entry_price.toLocaleString('en-US', { minimumFractionDigits: 2 })}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-0.5">Stop loss</p>
              <p className="font-mono text-red-400">${pos.stop_loss.toLocaleString('en-US', { minimumFractionDigits: 2 })}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-0.5">Take profit</p>
              <p className="font-mono text-emerald-400">${pos.take_profit.toLocaleString('en-US', { minimumFractionDigits: 2 })}</p>
            </div>
          </div>
        </div>
      ) : (
        <div className="sm:col-span-2 lg:col-span-3 bg-gray-900 rounded-2xl border border-gray-800 p-4 flex items-center gap-2 text-sm text-gray-500">
          <TrendingUp size={14} />
          <span>No open position — bot is looking for entry signals</span>
        </div>
      )}

      {/* Circuit breaker — full width */}
      <div className="sm:col-span-2 lg:col-span-3 bg-gray-900 rounded-2xl border border-gray-800 p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-gray-400">
            <Shield size={14} />
            <span>Circuit breaker</span>
          </div>
          {status.circuit_breaker_active ? (
            <div className="flex items-center gap-1.5 text-sm text-red-400 font-medium">
              <XCircle size={14} />
              Active — signal publishing paused today
            </div>
          ) : (
            <div className="flex items-center gap-1.5 text-sm text-emerald-400 font-medium">
              <CheckCircle size={14} />
              Inactive — within daily loss limit
            </div>
          )}
        </div>
      </div>

    </div>
  )
}

function InfoCard({
  label, value, sub, subColor = 'text-gray-500',
}: { label: string; value: string; sub?: string; subColor?: string }) {
  return (
    <div className="bg-gray-900 rounded-2xl border border-gray-800 p-4">
      <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">{label}</p>
      <p className="text-lg font-bold text-gray-100">{value}</p>
      {sub && <p className={`text-xs mt-0.5 ${subColor}`}>{sub}</p>}
    </div>
  )
}
