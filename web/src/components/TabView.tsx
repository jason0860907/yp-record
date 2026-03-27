import { useStore } from '../store/useStore'
import LiveTranscriptView from './LiveTranscriptView'
import AlignmentView from './AlignmentView'
import MeetingNoteView from './MeetingNoteView'
import ActionBar from './ActionBar'

interface Props {
  sessionId: string | null
}

export default function TabView({ sessionId }: Props) {
  const activeTab = useStore((s) => s.activeTab)
  const setActiveTab = useStore((s) => s.setActiveTab)

  const tabs = [
    { id: 'live' as const, label: 'Live Transcript' },
    { id: 'alignment' as const, label: 'Alignment' },
    { id: 'note' as const, label: 'Meeting Note' },
  ]

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      {/* Tab headers + actions */}
      <div className="flex items-center border-b border-slate-200/40 px-4">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`relative px-4 py-3 text-sm font-medium transition-colors duration-200 cursor-pointer ${
              activeTab === tab.id
                ? 'text-accent'
                : 'text-slate-400 hover:text-slate-600'
            }`}
          >
            {tab.label}
            {activeTab === tab.id && (
              <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-accent rounded-t-full" />
            )}
          </button>
        ))}
        {sessionId && (
          <div className="ml-auto">
            <ActionBar sessionId={sessionId} />
          </div>
        )}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-hidden">
        {activeTab === 'live' ? (
          <LiveTranscriptView sessionId={sessionId} />
        ) : activeTab === 'alignment' && sessionId ? (
          <AlignmentView sessionId={sessionId} />
        ) : activeTab === 'note' && sessionId ? (
          <MeetingNoteView sessionId={sessionId} />
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-slate-400">
            Select a session to view
          </div>
        )}
      </div>
    </div>
  )
}
