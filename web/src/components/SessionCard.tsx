import { Mic, Trash2 } from 'lucide-react'
import type { SessionInfo } from '../types'

interface Props {
  session: SessionInfo
  isActive: boolean
  onClick: () => void
  onDelete?: (id: string) => void
}

function formatDuration(secs: number): string {
  const m = Math.floor(secs / 60)
  const s = Math.floor(secs % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

function formatDate(iso: string | null): string {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export default function SessionCard({ session, isActive, onClick, onDelete }: Props) {
  const isRecording = session.status === 'recording' || session.status === 'paused'

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onClick() }}
      className={`w-full text-left px-3 py-2.5 rounded-xl transition-all duration-200 cursor-pointer group ${
        isActive
          ? 'bg-white/70 text-slate-800 shadow-sm'
          : 'text-slate-600 hover:bg-white/40 hover:text-slate-800'
      }`}
    >
      <div className="flex items-start gap-2.5">
        {isRecording && (
          <span className="mt-1 h-2 w-2 flex-shrink-0 rounded-full bg-red-500 animate-pulse-ring" />
        )}
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium leading-tight">
            {session.title || `Session ${session.id.slice(0, 6)}`}
          </p>
          <p className="mt-1 text-xs text-slate-400 font-mono">
            {formatDate(session.started_at)}
          </p>
          <div className="mt-1.5 flex items-center gap-2.5 text-xs text-slate-400">
            <span className="flex items-center gap-1">
              <Mic className="h-3 w-3" />
              {session.segment_count}
            </span>
            {session.duration_seconds > 0 && (
              <span className="font-mono">{formatDuration(session.duration_seconds)}</span>
            )}
          </div>
        </div>
        {onDelete && !isRecording && (
          <button
            onClick={(e) => {
              e.stopPropagation()
              onDelete(session.id)
            }}
            title="Delete session"
            className="flex h-6 w-6 items-center justify-center rounded-lg opacity-0 group-hover:opacity-100 text-slate-400 hover:text-red-500 hover:bg-red-50 transition-all duration-200 cursor-pointer flex-shrink-0 mt-0.5"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
    </div>
  )
}
