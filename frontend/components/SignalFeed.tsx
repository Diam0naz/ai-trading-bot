'use client'
import useSWR from 'swr'
import { getSignals } from '@/lib/api'
import SignalCard from './SignalCard'
import type { Signal } from '@/lib/types'
import { RefreshCw } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { useState, useEffect } from 'react'

interface Props {
  initialSignals: Signal[]
}

export default function SignalFeed({ initialSignals }: Props) {
  const { data: signals = initialSignals, isValidating } = useSWR<Signal[]>(
    'signals-feed',
    () => getSignals(20),
    { refreshInterval: 30000, fallbackData: initialSignals }
  )

  const [lastRefreshed, setLastRefreshed] = useState(new Date())
  useEffect(() => {
    if (!isValidating) setLastRefreshed(new Date())
  }, [isValidating])

  return (
    <div>
      {/* Refresh indicator */}
      <div className="flex items-center gap-2 mb-5 text-xs text-gray-500">
        <RefreshCw
          size={11}
          className={isValidating ? 'animate-spin text-teal-400' : ''}
        />
        <span>
          {isValidating
            ? 'Refreshing…'
            : `Updated ${formatDistanceToNow(lastRefreshed, { addSuffix: true })}`}
        </span>
        <span className="text-gray-700">· auto-refresh every 30s</span>
      </div>

      {signals.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <div className="w-12 h-12 rounded-full bg-gray-800 flex items-center justify-center mb-4">
            <RefreshCw size={20} className="text-gray-600" />
          </div>
          <p className="text-gray-400 font-medium">No signals yet</p>
          <p className="text-gray-600 text-sm mt-1">
            The bot will post here when it generates its first signal.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {signals.map((s) => (
            <SignalCard key={s.id} signal={s} />
          ))}
        </div>
      )}
    </div>
  )
}
