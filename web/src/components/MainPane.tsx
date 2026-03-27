import { Mic } from 'lucide-react'
import { useStore } from '../store/useStore'
import RecordingHeader from './RecordingHeader'
import TabView from './TabView'

export default function MainPane() {
  const activeSession = useStore((s) => s.activeSession)
  const selectedSessionId = useStore((s) => s.selectedSessionId)

  const sessionId = activeSession?.id ?? selectedSessionId

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <RecordingHeader />
      {sessionId ? (
        <TabView sessionId={sessionId} />
      ) : (
        <div className="flex flex-1 flex-col items-center justify-center gap-4">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-accent/[0.06]">
            <Mic className="h-7 w-7 text-accent/40" />
          </div>
          <div className="text-center">
            <p className="text-sm font-medium text-slate-500">No session selected</p>
            <p className="text-xs text-slate-400 mt-1.5">Click + in the sidebar to start recording</p>
          </div>
        </div>
      )}
    </div>
  )
}
