import { create } from 'zustand'
import type { SessionInfo, TranscriptSegment } from '../types'

interface RecordStore {
  // Active session
  activeSession: SessionInfo | null
  segments: TranscriptSegment[]
  micEnabled: boolean
  micLevel: number
  tabLevel: number

  // Session list
  sessions: SessionInfo[]

  // UI state
  selectedSessionId: string | null
  activeTab: 'live' | 'alignment' | 'note'
  connected: boolean

  // Actions
  setActiveSession: (session: SessionInfo | null) => void
  setSegments: (segs: TranscriptSegment[]) => void
  addSegment: (seg: TranscriptSegment) => void
  clearSession: () => void
  setMicEnabled: (v: boolean) => void
  setAudioLevels: (mic: number, tab: number) => void
  setSessions: (sessions: SessionInfo[]) => void
  setSelectedSessionId: (id: string | null) => void
  setActiveTab: (tab: 'live' | 'alignment' | 'note') => void
  setConnected: (v: boolean) => void
}

export const useStore = create<RecordStore>((set) => ({
  activeSession: null,
  segments: [],
  micEnabled: true,
  micLevel: 0,
  tabLevel: 0,
  sessions: [],
  selectedSessionId: null,
  activeTab: 'live',
  connected: false,

  setActiveSession: (session) => set({ activeSession: session }),
  setSegments: (segments) => set({ segments }),
  addSegment: (seg) => set((s) => ({ segments: [...s.segments, seg] })),
  clearSession: () => set({ segments: [], activeSession: null, activeTab: 'live' }),
  setMicEnabled: (micEnabled) => set({ micEnabled }),
  setAudioLevels: (micLevel, tabLevel) => set({ micLevel, tabLevel }),
  setSessions: (sessions) => set({ sessions }),
  setSelectedSessionId: (selectedSessionId) => set({ selectedSessionId }),
  setActiveTab: (activeTab) => set({ activeTab }),
  setConnected: (connected) => set({ connected }),
}))
