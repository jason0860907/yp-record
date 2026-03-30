export type SessionStatus = 'idle' | 'recording' | 'paused' | 'processing' | 'completed' | 'error'
export type SessionSource = 'recording' | 'youtube'

export interface SessionInfo {
  id: string
  status: SessionStatus
  source?: SessionSource
  source_url?: string | null
  title: string | null
  started_at: string | null
  ended_at: string | null
  duration_seconds: number
  segment_count: number
  participants: string[]
}

export interface TranscriptSegment {
  id: string
  text: string
  speaker: 'self' | 'other' | 'unknown'
  channel: number
  start_time: number
  end_time: number
  language: string
  timestamp: string
}

export interface WordTimestamp {
  word: string
  start: number
  end: number
  score: number
}

export interface EnrichedTranscriptSegment {
  id: string
  text: string
  start: number
  end: number
  speaker: string | null
  words: WordTimestamp[]
  language: string
}

export interface AlignmentResult {
  session_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'not_started'
  language: string
  segments: EnrichedTranscriptSegment[]
  num_speakers: number
  processing_time_seconds: number
  created_at: string
  error: string | null
}

export interface AlignmentStatus {
  session_id: string
  status: string
  num_segments: number
  num_speakers: number
  processing_time_seconds: number
  error: string | null
  audio_available: boolean
  wav_available: boolean
  service_available: boolean
}

export interface AppConfig {
  notion_enabled: boolean
  aligner_enabled: boolean
  diarization_enabled: boolean
  extract_enabled: boolean
  screenshot_interval_seconds: number
}

export interface MeetingNote {
  session_id: string
  title: string
  content: string
  category: string
  tags: string[]
  created_at: string
}

export interface ExtractResult {
  session_id: string
  has_polished_transcript: boolean
  meeting_note_title: string | null
}
