'use client'
import useSWR from 'swr'
import { getCandles, getSignals } from '@/lib/api'
import CandleChart from '@/components/CandleChart'
import type { Candle, Signal } from '@/lib/types'
import { RefreshCw, TrendingUp } from 'lucide-react'

export default function ChartPage() {
  const { data: candles = [], isLoading: cl, isValidating: cv } = useSWR<Candle[]>(
    'candles',
    () => getCandles('BTC/USDT', '4h', 200),
    { refreshInterval: 60000 }
  )
  const { data: signals = [], isLoading: sl } = useSWR<Signal[]>(
    'signals-chart',
    () => getSignals(50),
    { refreshInterval: 30000 }
  )

  const loading = cl || sl

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Price chart</h1>
          <p className="text-sm text-gray-500 mt-1">BTC/USDT · 4h · signal markers overlaid</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <RefreshCw size={11} className={cv ? 'animate-spin text-teal-400' : ''} />
          <span>{cv ? 'Updating…' : 'Updates every 60s'}</span>
        </div>
      </div>

      {loading ? (
        <div className="h-[26rem] bg-gray-900 rounded-2xl border border-gray-800 flex items-center justify-center">
          <div className="flex flex-col items-center gap-3 text-gray-600">
            <RefreshCw size={24} className="animate-spin" />
            <span className="text-sm">Loading chart data…</span>
          </div>
        </div>
      ) : (
        <CandleChart candles={candles} signals={signals} />
      )}

      {/* Legend */}
      {!loading && (
        <div className="flex items-center gap-6 mt-4 text-xs text-gray-500">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400 inline-block" />
            Green candle / BUY marker
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-red-400 inline-block" />
            Red candle / SELL marker
          </span>
          <span className="flex items-center gap-1.5">
            <TrendingUp size={11} />
            Arrow markers show signal confidence %
          </span>
        </div>
      )}
    </div>
  )
}
