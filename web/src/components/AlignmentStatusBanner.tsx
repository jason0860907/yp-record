import { Loader2, AlertCircle, Wand2 } from 'lucide-react'
import { triggerAlignment } from '../api/client'
import { useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import type { AlignmentStatus } from '../types'

interface Props {
  sessionId: string
  status: AlignmentStatus | null
  serviceAvailable: boolean
}

export default function AlignmentStatusBanner({ sessionId, status, serviceAvailable }: Props) {
  const queryClient = useQueryClient()

  const handleTrigger = async () => {
    try {
      await triggerAlignment(sessionId)
      queryClient.invalidateQueries({ queryKey: ['alignment-status', sessionId] })
      toast.success('Alignment started')
    } catch {
      toast.error('Failed to trigger alignment')
    }
  }

  if (!status || status.status === 'not_started') {
    if (!serviceAvailable) {
      return (
        <div className="rounded-xl bg-amber-50/70 border border-amber-200/50 px-4 py-3 text-sm text-amber-700">
          Forced aligner not available. Check server configuration.
        </div>
      )
    }
    if (!status?.audio_available) {
      return (
        <div className="rounded-xl bg-white/30 backdrop-blur-sm border border-white/40 px-4 py-3 text-sm text-slate-500">
          No audio recorded for this session.
        </div>
      )
    }
    return (
      <div className="flex items-center justify-between rounded-xl bg-indigo-50/60 border border-indigo-200/40 px-4 py-3">
        <p className="text-sm text-indigo-600">Alignment not yet processed.</p>
        <button
          onClick={handleTrigger}
          className="flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-dark transition-all duration-200 cursor-pointer shadow-sm"
        >
          <Wand2 className="h-3 w-3" />
          Process
        </button>
      </div>
    )
  }

  if (status.status === 'processing') {
    return (
      <div className="flex items-center gap-3 rounded-xl bg-blue-50/60 border border-blue-200/40 px-4 py-3 text-sm text-blue-600">
        <Loader2 className="h-4 w-4 animate-spin flex-shrink-0" />
        <span>Processing alignment... this may take a few minutes.</span>
      </div>
    )
  }

  if (status.status === 'failed') {
    return (
      <div className="flex items-center justify-between rounded-xl bg-red-50/60 border border-red-200/40 px-4 py-3">
        <div className="flex items-center gap-2 text-sm text-red-600">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          <span>Alignment failed: {status.error || 'Unknown error'}</span>
        </div>
        <button
          onClick={handleTrigger}
          className="flex items-center gap-1.5 rounded-lg bg-red-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-600 transition-all duration-200 cursor-pointer ml-4"
        >
          Retry
        </button>
      </div>
    )
  }

  return null
}
