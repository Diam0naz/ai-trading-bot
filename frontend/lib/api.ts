import type { BotStatus, Candle, DailyStat, PnLSummary, Signal, Trade } from './types'

async function fetchApi<T>(url: string): Promise<T> {
  const res = await fetch(url, { cache: 'no-store' })
  if (!res.ok) throw new Error(`API error ${res.status}: ${url}`)
  return res.json() as Promise<T>
}

export const getSignals = (limit = 20): Promise<Signal[]> =>
  fetchApi<Signal[]>(`/api/signals?limit=${limit}`)

export const getCandles = (symbol: string, timeframe: string, limit: number): Promise<Candle[]> =>
  fetchApi<Candle[]>(`/api/candles?symbol=${encodeURIComponent(symbol)}&timeframe=${timeframe}&limit=${limit}`)

export const getPnL = (days: number): Promise<DailyStat[]> =>
  fetchApi<DailyStat[]>(`/api/pnl?days=${days}`)

export const getPnLSummary = (): Promise<PnLSummary> =>
  fetchApi<PnLSummary>('/api/pnl/summary')

export const getBotStatus = (): Promise<BotStatus> =>
  fetchApi<BotStatus>('/api/status')

export const getTrades = (limit = 50): Promise<Trade[]> =>
  fetchApi<Trade[]>(`/api/trades?limit=${limit}`)
