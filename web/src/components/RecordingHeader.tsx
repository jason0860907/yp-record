import { useState, useEffect } from 'react'
import { Mic, MicOff, Wifi, WifiOff, Square, Pause, Play, AlertCircle } from 'lucide-react'
import { useStore } from '../store/useStore'
import { updateSession } from '../api/client'
import { useSession } from '../hooks/useSession'
import toast from 'react-hot-toast'

export default function RecordingHeader() {
  const activeSession = useStore((s) => s.activeSession)
  const setActiveSession = useStore((s) => s.setActiveSession)
  const micEnabled = useStore((s) => s.micEnabled)
  const setMicEnabled = useStore((s) => s.setMicEnabled)
  const connected = useStore((s) => s.connected)
  const micLevel = useStore((s) => s.micLevel)
  const tabLevel = useStore((s) => s.tabLevel)

  const { isRecording, isCapturing, captureError, startSession, pauseSession, resumeSession, endSession } = useSession()

  const [title, setTitle] = useState(activeSession?.title || '')
  const [editing, setEditing] = useState(false)

  useEffect(() => {
    setTitle(activeSession?.title || '')
  }, [activeSession?.id])

  const handleTitleBlur = async () => {
    setEditing(false)
    if (!activeSession || title === activeSession.title) return
    try {
      const updated = await updateSession(activeSession.id, { title: title || undefined })
      setActiveSession(updated)
    } catch {
      setTitle(activeSession.title || '')
    }
  }

  const handleStart = async () => {
    try { await startSession() }
    catch (err) { toast.error(err instanceof Error ? err.message : 'Failed to start') }
  }
  const handlePause = async () => {
    try { await pauseSession() } catch { toast.error('Failed to pause') }
  }
  const handleResume = async () => {
    try { await resumeSession() } catch { toast.error('Failed to resume') }
  }
  const handleEnd = async () => {
    try { await endSession() } catch { toast.error('Failed to stop') }
  }

  const status = activeSession?.status
  const isActiveRecording = status === 'recording'

  return (
    <div className={`flex items-center gap-3 px-5 py-3 border-b border-slate-200/40 flex-shrink-0 transition-all duration-300 ${
      isActiveRecording ? 'bg-red-50/60' : ''
    }`}>
      {/* Status indicator */}
      {isActiveRecording ? (
        <span className="flex-shrink-0 rounded-md bg-red-500 px-1.5 py-0.5 text-[10px] font-bold text-white tracking-wider">REC</span>
      ) : (
        <span className={`h-2 w-2 rounded-full flex-shrink-0 ${
          status === 'paused'    ? 'bg-amber-500' :
          status === 'completed' ? 'bg-emerald-500' :
                                   'bg-slate-300'
        }`} />
      )}

      {/* Title */}
      <div className="flex-1 min-w-0">
        {activeSession ? (
          editing ? (
            <input
              autoFocus
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              onBlur={handleTitleBlur}
              onKeyDown={(e) => e.key === 'Enter' && handleTitleBlur()}
              className="w-full bg-transparent text-sm font-semibold text-slate-800 outline-none border-b border-accent/40 pb-px"
              placeholder="Session title"
            />
          ) : (
            <button
              onClick={() => setEditing(true)}
              className="block truncate text-left text-sm font-semibold text-slate-700 hover:text-accent transition-colors duration-200 cursor-pointer max-w-full"
            >
              {activeSession.title || `Session ${activeSession.id.slice(0, 6)}`}
            </button>
          )
        ) : (
          <span className="text-sm text-slate-400">Click + to start a new session</span>
        )}
      </div>

      {/* Capture error */}
      {captureError && (
        <div className="flex items-center gap-1.5 rounded-lg bg-red-50 border border-red-200/50 px-2.5 py-1 text-xs text-red-600 flex-shrink-0 max-w-[220px]">
          <AlertCircle className="h-3 w-3 flex-shrink-0" />
          <span className="truncate">{captureError}</span>
        </div>
      )}

      {/* Level meters (only while recording) */}
      {isRecording && (
        <div className="flex items-center gap-3 flex-shrink-0">
          <LevelMeter level={micLevel} label="Mic" color="bg-accent" />
          <LevelMeter level={tabLevel} label="Tab" color="bg-emerald-500" />
        </div>
      )}

      {/* Connection */}
      <div className="flex-shrink-0" title={connected ? 'Connected' : 'Disconnected'}>
        {connected
          ? <Wifi className="h-3.5 w-3.5 text-emerald-500" />
          : <WifiOff className="h-3.5 w-3.5 text-slate-300" />
        }
      </div>

      {/* Mic toggle */}
      <button
        onClick={() => setMicEnabled(!micEnabled)}
        disabled={isRecording}
        title={micEnabled ? 'Mic on' : 'Mic off'}
        className={`flex h-8 w-8 items-center justify-center rounded-lg transition-all duration-200 cursor-pointer flex-shrink-0 disabled:opacity-40 disabled:cursor-not-allowed ${
          micEnabled
            ? 'bg-accent/[0.08] text-accent hover:bg-accent/[0.15]'
            : 'bg-slate-100/60 text-slate-400 hover:bg-slate-200/60'
        }`}
      >
        {micEnabled ? <Mic className="h-3.5 w-3.5" /> : <MicOff className="h-3.5 w-3.5" />}
      </button>

      {/* Record controls */}
      {activeSession && (
        <div className="flex items-center gap-1.5 flex-shrink-0">
          {status === 'idle' && (
            <button
              onClick={handleStart}
              disabled={isCapturing}
              className="flex items-center gap-1.5 rounded-lg bg-red-500 px-3.5 py-2 text-xs font-medium text-white hover:bg-red-600 disabled:opacity-50 transition-all duration-200 cursor-pointer shadow-sm"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-white flex-shrink-0" />
              Record
            </button>
          )}

          {status === 'recording' && (
            <>
              <button
                onClick={handlePause}
                title="Pause"
                className="flex h-9 w-9 items-center justify-center rounded-lg bg-white/50 border border-red-200/50 text-red-500 hover:bg-red-50 transition-all duration-200 cursor-pointer"
              >
                <Pause className="h-4 w-4" />
              </button>
              <button
                onClick={handleEnd}
                title="Stop recording"
                className="flex h-9 items-center gap-1.5 rounded-lg bg-red-500 px-3.5 text-xs font-medium text-white hover:bg-red-600 transition-all duration-200 cursor-pointer shadow-sm"
              >
                <Square className="h-3 w-3 fill-current" />
                Stop
              </button>
            </>
          )}

          {status === 'paused' && (
            <>
              <button
                onClick={handleResume}
                title="Resume"
                className="flex h-9 w-9 items-center justify-center rounded-lg bg-white/50 border border-accent/20 text-accent hover:bg-accent/[0.06] transition-all duration-200 cursor-pointer"
              >
                <Play className="h-4 w-4 ml-px" />
              </button>
              <button
                onClick={handleEnd}
                title="Stop"
                className="flex h-9 items-center gap-1.5 rounded-lg bg-slate-600 px-3.5 text-xs font-medium text-white hover:bg-slate-700 transition-all duration-200 cursor-pointer"
              >
                <Square className="h-3 w-3 fill-current" />
                Stop
              </button>
            </>
          )}
        </div>
      )}
    </div>
  )
}

function LevelMeter({ level, label, color }: { level: number; label: string; color: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-[10px] font-mono text-slate-400 w-5 uppercase tracking-wider">{label}</span>
      <div className="h-1.5 w-16 rounded-full bg-slate-200/60 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-75 ${color}`}
          style={{ width: `${Math.round(level * 100)}%` }}
        />
      </div>
    </div>
  )
}
