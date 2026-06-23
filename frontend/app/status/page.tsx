'use client'
import useSWR from 'swr'
import { getBotStatus } from '@/lib/api'
import BotStatusCard from '@/components/BotStatus'
import type { BotStatus } from '@/lib/types'
import { RefreshCw } from 'lucide-react'

export default function StatusPage() {
  const { data, isLoading, error, isValidating } = useSWR<BotStatus>(
    'status',
    getBotStatus,
    { refreshInterval: 15000 }
  )

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Bot status</h1>
          <p className="text-sm text-gray-500 mt-1">Live health check · refreshes every 15s</p>
        </div>
        <RefreshCw
          size={14}
          className={`text-gray-500 ${isValidating ? 'animate-spin text-teal-400' : ''}`}
        />
      </div>

      {isLoading && (
        <div className="bg-gray-900 rounded-2xl border border-gray-800 p-8 animate-pulse">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-4 h-4 rounded-full bg-gray-700" />
            <div className="h-4 w-28 rounded bg-gray-700" />
          </div>
          <div className="space-y-3">
            {[1,2,3,4].map(i => (
              <div key={i} className="flex justify-between">
                <div className="h-3 w-20 rounded bg-gray-800" />
                <div className="h-3 w-28 rounded bg-gray-800" />
              </div>
            ))}
          </div>
        </div>
      )}

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-2xl p-5">
          <p className="text-red-400 text-sm font-medium">Failed to load bot status</p>
          <p className="text-red-500/70 text-xs mt-1">{(error as Error).message}</p>
        </div>
      )}

      {data && <BotStatusCard status={data} />}
    </div>
  )
}
