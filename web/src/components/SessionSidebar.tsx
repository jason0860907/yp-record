import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Loader2 } from 'lucide-react'
import { listSessions, deleteSession } from '../api/client'
import { useStore } from '../store/useStore'
import { useSession } from '../hooks/useSession'
import SessionCard from './SessionCard'
import toast from 'react-hot-toast'

export default function SessionSidebar() {
  const queryClient = useQueryClient()

  const { data: sessions = [], isLoading } = useQuery({
    queryKey: ['sessions'],
    queryFn: listSessions,
    refetchInterval: 5000,
  })

  const activeSession = useStore((s) => s.activeSession)
  const selectedSessionId = useStore((s) => s.selectedSessionId)
  const setSelectedSessionId = useStore((s) => s.setSelectedSessionId)
  const clearSession = useStore((s) => s.clearSession)
  const { createSession } = useSession()

  const handleSelectSession = (id: string) => {
    setSelectedSessionId(id)
  }

  const handleNewSession = async () => {
    await createSession()
    setSelectedSessionId(null)
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
        <button
          onClick={handleNewSession}
          className="flex h-7 w-7 items-center justify-center rounded-lg text-slate-400 hover:text-accent hover:bg-accent/[0.08] transition-all duration-200 cursor-pointer"
          title="New session"
        >
          <Plus className="h-4 w-4" />
        </button>
      </div>

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
