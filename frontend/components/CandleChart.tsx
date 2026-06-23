'use client'
import { useEffect, useRef, useState } from 'react'
import Script from 'next/script'
import type { Candle, Signal } from '@/lib/types'

interface LWCChart {
  addCandlestickSeries: (opts: Record<string, unknown>) => LWCSeries
  resize: (w: number, h: number) => void
  remove: () => void
}

interface LWCSeries {
  setData: (data: unknown[]) => void
  setMarkers: (markers: unknown[]) => void
}

interface LightweightChartsGlobal {
  createChart: (el: HTMLElement, opts: Record<string, unknown>) => LWCChart
}

interface Props {
  candles: Candle[]
  signals: Signal[]
}

export default function CandleChart({ candles, signals }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<LWCChart | null>(null)
  // Track when the CDN script has finished loading
  const [scriptReady, setScriptReady] = useState(false)

  useEffect(() => {
    // Wait for both the script and the candle data
    if (!scriptReady || !containerRef.current || candles.length === 0) return

    const LWC = (window as unknown as { LightweightCharts?: LightweightChartsGlobal })
      .LightweightCharts
    if (!LWC) return

    // Tear down any previous chart instance
    chartRef.current?.remove()

    const chart = LWC.createChart(containerRef.current, {
      layout: { background: { color: '#000000' }, textColor: '#9ca3af' },
      grid: {
        vertLines: { color: '#111827' },
        horzLines: { color: '#111827' },
      },
      timeScale: { borderColor: '#374151' },
      width: containerRef.current.clientWidth,
      height: 384,
    })

    const series = chart.addCandlestickSeries({
      upColor: '#10b981',
      downColor: '#ef4444',
      borderUpColor: '#10b981',
      borderDownColor: '#ef4444',
      wickUpColor: '#10b981',
      wickDownColor: '#ef4444',
    })

    series.setData(
      candles.map((c) => ({
        time: Math.floor(c.timestamp / 1000),
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }))
    )

    const markers = signals
      .filter((s) => s.direction !== 'HOLD')
      .map((s) => ({
        time: Math.floor(s.timestamp / 1000),
        position: s.direction === 'BUY' ? 'belowBar' : 'aboveBar',
        color: s.direction === 'BUY' ? '#10b981' : '#ef4444',
        shape: s.direction === 'BUY' ? 'arrowUp' : 'arrowDown',
        text: `${s.direction} ${(s.confidence * 100).toFixed(0)}%`,
      }))
    series.setMarkers(markers)

    chartRef.current = chart

    const ro = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.resize(containerRef.current.clientWidth, 384)
      }
    })
    ro.observe(containerRef.current)

    return () => {
      ro.disconnect()
      chart.remove()
      chartRef.current = null
    }
  }, [scriptReady, candles, signals])

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
      {/*
        next/script with strategy="afterInteractive" guarantees the script runs
        after hydration. onLoad fires in the same tick, setting scriptReady=true
        which triggers the useEffect above to initialise the chart.
      */}
      {/* Pinned to v4.2.2 — v5 removed addCandlestickSeries and setMarkers */}
      <Script
        src="https://unpkg.com/lightweight-charts@4.2.2/dist/lightweight-charts.standalone.production.js"
        strategy="afterInteractive"
        onLoad={() => setScriptReady(true)}
      />
      <div ref={containerRef} className="w-full h-96" />
      {candles.length === 0 && (
        <p className="text-center text-gray-600 text-sm py-8">
          No candle data yet. The bot will populate this once it starts running.
        </p>
      )}
    </div>
  )
}
