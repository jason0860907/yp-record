import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Loader2, X } from 'lucide-react'
import { listSessions, deleteSession, importYouTube } from '../api/client'
import { useStore } from '../store/useStore'
import { useSession } from '../hooks/useSession'
import { useTranscriptStream } from '../hooks/useTranscriptStream'
import SessionCard from './SessionCard'
import toast from 'react-hot-toast'
import type { SessionInfo } from '../types'

export default function SessionSidebar() {
  const queryClient = useQueryClient()
  const [showYtInput, setShowYtInput] = useState(false)
  const [ytUrl, setYtUrl] = useState('')
  const [ytLoading, setYtLoading] = useState(false)

  const { data: sessions = [], isLoading } = useQuery({
    queryKey: ['sessions'],
    queryFn: listSessions,
    refetchInterval: 5000,
  })

  const activeSession = useStore((s) => s.activeSession)
  const setActiveSession = useStore((s) => s.setActiveSession)
  const selectedSessionId = useStore((s) => s.selectedSessionId)
  const setSelectedSessionId = useStore((s) => s.setSelectedSessionId)
  const clearSession = useStore((s) => s.clearSession)
  const setYtImportProgress = useStore((s) => s.setYtImportProgress)
  const { createSession } = useSession()
  const { connect: connectTranscript } = useTranscriptStream()

  const handleSelectSession = (id: string) => {
    setSelectedSessionId(id)
  }

  const handleNewSession = async () => {
    await createSession()
    setSelectedSessionId(null)
  }

  const handleYtImport = async () => {
    const url = ytUrl.trim()
    if (!url) return
    setYtLoading(true)
    try {
      const session = await importYouTube(url)
      setActiveSession(session as SessionInfo)
      setSelectedSessionId(null)
      setYtImportProgress({ status: 'downloading', percent: 0, currentChunk: 0, totalChunks: 0 })
      connectTranscript(session.id)
      queryClient.invalidateQueries({ queryKey: ['sessions'] })
      setShowYtInput(false)
      setYtUrl('')
      toast.success('YouTube import started')
    } catch {
      toast.error('Failed to start YouTube import')
    } finally {
      setYtLoading(false)
    }
  }

  const handleDelete = async (id: string) => {
    if (activeSession?.id === id && (activeSession.status === 'recording' || activeSession.status === 'paused')) {
      toast.error('Stop recording before deleting')
      return
    }
    if (!window.confirm('Delete this session? This cannot be undone.')) return
    try {
      await deleteSession(id)
      if (selectedSessionId === id) setSelectedSessionId(null)
      if (activeSession?.id === id) clearSession()
      queryClient.invalidateQueries({ queryKey: ['sessions'] })
      toast.success('Session deleted')
    } catch {
      toast.error('Failed to delete session')
    }
  }

  const allSessions = sessions
  const hasActive = activeSession && !allSessions.find((s) => s.id === activeSession.id)
  const displaySessions = hasActive ? [activeSession, ...allSessions] : allSessions

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200/50">
        <h1 className="text-sm font-semibold text-slate-700 tracking-tight">
          YP-Record
        </h1>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setShowYtInput(!showYtInput)}
            className={`flex h-7 w-7 items-center justify-center rounded-lg transition-all duration-200 cursor-pointer ${
              showYtInput
                ? 'bg-red-50'
                : 'hover:bg-red-50'
            }`}
            title="Import YouTube video"
          >
            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none">
              <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.546 12 3.546 12 3.546s-7.505 0-9.377.504A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.504 9.376.504 9.376.504s7.505 0 9.377-.504a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814Z" fill="#FF0000"/>
              <path d="m9.545 15.568 6.273-3.568-6.273-3.568v7.136Z" fill="#fff"/>
            </svg>
          </button>
          <button
            onClick={handleNewSession}
            className="flex h-7 w-7 items-center justify-center rounded-lg text-slate-400 hover:text-accent hover:bg-accent/[0.08] transition-all duration-200 cursor-pointer"
            title="New session"
          >
            <Plus className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* YouTube URL input */}
      {showYtInput && (
        <div className="px-3 py-2.5 border-b border-slate-200/50">
          <div className="flex items-center gap-1.5">
            <input
              autoFocus
              type="url"
              value={ytUrl}
              onChange={(e) => setYtUrl(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleYtImport()}
              placeholder="Paste YouTube URL..."
              className="flex-1 min-w-0 rounded-lg bg-white/60 border border-slate-200/60 px-2.5 py-1.5 text-xs text-slate-700 placeholder:text-slate-400 outline-none focus:border-accent/40 focus:ring-1 focus:ring-accent/20 transition-all"
            />
            <button
              onClick={handleYtImport}
              disabled={ytLoading || !ytUrl.trim()}
              className="flex h-7 items-center gap-1 rounded-lg bg-accent px-2.5 text-xs font-medium text-white hover:bg-accent-dark disabled:opacity-50 transition-all duration-200 cursor-pointer shadow-sm flex-shrink-0"
            >
              {ytLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Go'}
            </button>
            <button
              onClick={() => { setShowYtInput(false); setYtUrl('') }}
              className="flex h-7 w-7 items-center justify-center rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100/60 transition-all duration-200 cursor-pointer flex-shrink-0"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Session list */}
      <div className="flex-1 overflow-y-auto px-2 py-2 space-y-1 scrollbar-thin">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center py-8 gap-2 text-slate-400">
            <Loader2 className="h-5 w-5 animate-spin" />
            <p className="text-xs">Loading sessions...</p>
          </div>
        ) : displaySessions.length === 0 ? (
          <p className="px-3 py-8 text-center text-xs text-slate-400">
            No sessions yet.
            <br />
            Click + to start.
          </p>
        ) : (
          displaySessions.map((session) => (
            <SessionCard
              key={session.id}
              session={session}
              isActive={
                (activeSession?.id === session.id && !selectedSessionId) ||
                selectedSessionId === session.id
              }
              onClick={() => handleSelectSession(session.id)}
              onDelete={handleDelete}
            />
          ))
        )}
      </div>
    </div>
  )
}
