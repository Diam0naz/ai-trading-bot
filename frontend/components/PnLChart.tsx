'use client'
import {
  CartesianGrid, Line, LineChart, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis, Area, AreaChart,
} from 'recharts'
import { format, parseISO } from 'date-fns'
import type { DailyStat } from '@/lib/types'

interface Props { data: DailyStat[] }

// Compute cumulative PnL for the area chart
function withCumulative(data: DailyStat[]) {
  let cum = 0
  return data.map(d => {
    cum += d.pnl_pct
    return { ...d, cumulative_pnl: cum }
  })
}

export default function PnLChart({ data }: Props) {
  if (data.length === 0) {
    return (
      <div className="h-64 flex items-center justify-center text-gray-600 text-sm">
        No performance data yet — run the bot for a day to see results here.
      </div>
    )
  }

  const enriched = withCumulative(data)
  const isPositive = enriched[enriched.length - 1].cumulative_pnl >= 0

  return (
    <div className="space-y-6">
      {/* Cumulative PnL area chart */}
      <div>
        <p className="text-xs text-gray-500 mb-3">Cumulative PnL %</p>
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={enriched} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="pnlGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor={isPositive ? '#34d399' : '#f87171'} stopOpacity={0.3} />
                <stop offset="95%" stopColor={isPositive ? '#34d399' : '#f87171'} stopOpacity={0}   />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
            <XAxis
              dataKey="date"
              tickFormatter={(d: string) => format(parseISO(d), 'MMM d')}
              stroke="#374151" tick={{ fill: '#6b7280', fontSize: 10 }}
              tickLine={false} axisLine={false}
            />
            <YAxis
              tickFormatter={(v: number) => `${v.toFixed(1)}%`}
              stroke="#374151" tick={{ fill: '#6b7280', fontSize: 10 }}
              tickLine={false} axisLine={false} width={44}
            />
            <Tooltip
              contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 10, fontSize: 12 }}
              formatter={(v) => [`${Number(v).toFixed(2)}%`, 'Cumulative PnL']}
              labelFormatter={(d) => format(parseISO(d as string), 'MMMM d, yyyy')}
              itemStyle={{ color: isPositive ? '#34d399' : '#f87171' }}
              labelStyle={{ color: '#9ca3af' }}
            />
            <ReferenceLine y={0} stroke="#374151" strokeDasharray="4 4" />
            <Area
              type="monotone" dataKey="cumulative_pnl"
              stroke={isPositive ? '#34d399' : '#f87171'} strokeWidth={2}
              fill="url(#pnlGradient)"
              dot={false} activeDot={{ r: 4, fill: isPositive ? '#34d399' : '#f87171' }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Daily PnL bar-line chart */}
      <div>
        <p className="text-xs text-gray-500 mb-3">Daily PnL %</p>
        <ResponsiveContainer width="100%" height={120}>
          <LineChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
            <XAxis
              dataKey="date"
              tickFormatter={(d: string) => format(parseISO(d), 'd')}
              stroke="#374151" tick={{ fill: '#6b7280', fontSize: 10 }}
              tickLine={false} axisLine={false}
            />
            <YAxis
              tickFormatter={(v: number) => `${v.toFixed(1)}%`}
              stroke="#374151" tick={{ fill: '#6b7280', fontSize: 10 }}
              tickLine={false} axisLine={false} width={44}
            />
            <Tooltip
              contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 10, fontSize: 12 }}
              formatter={(v) => [`${Number(v).toFixed(2)}%`, 'Daily PnL']}
              labelFormatter={(d) => format(parseISO(d as string), 'MMMM d, yyyy')}
              itemStyle={{ color: '#2dd4bf' }}
              labelStyle={{ color: '#9ca3af' }}
            />
            <ReferenceLine y={0} stroke="#374151" strokeDasharray="4 4" />
            <Line
              type="monotone" dataKey="pnl_pct"
              stroke="#2dd4bf" strokeWidth={1.5}
              dot={{ fill: '#2dd4bf', r: 2 }}
              activeDot={{ r: 4 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
