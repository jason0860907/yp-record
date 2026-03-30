import axios from 'axios'
import type { SessionInfo, AlignmentResult, AlignmentStatus, AppConfig, TranscriptSegment, MeetingNote, ExtractResult } from '../types'

const api = axios.create({ baseURL: '/api' })

// Sessions
export const createSession = (title?: string, participants?: string[]) =>
  api.post<SessionInfo>('/sessions', { title, participants }).then((r) => r.data)

export const listSessions = () =>
  api.get<{ sessions: SessionInfo[] }>('/sessions').then((r) => r.data.sessions)

export const getSession = (id: string) =>
  api.get<SessionInfo>(`/sessions/${id}`).then((r) => r.data)

export const updateSession = (id: string, patch: { title?: string; participants?: string[] }) =>
  api.patch<SessionInfo>(`/sessions/${id}`, patch).then((r) => r.data)

export const sessionAction = (id: string, action: 'start' | 'pause' | 'resume' | 'end') =>
  api.post<SessionInfo>(`/sessions/${id}/action`, { action }).then((r) => r.data)

export const deleteSession = (id: string) =>
  api.delete(`/sessions/${id}`).then((r) => r.data)

export const getSessionSegments = (id: string) =>
  api.get<{ segments: TranscriptSegment[] }>(`/sessions/${id}/segments`).then((r) => r.data.segments)

// Alignment
export const getAlignmentStatus = (id: string) =>
  api.get<AlignmentStatus>(`/sessions/${id}/alignment/status`).then((r) => r.data)

export const getAlignmentResult = (id: string) =>
  api.get<AlignmentResult>(`/sessions/${id}/alignment`).then((r) => r.data)

export const triggerAlignment = (id: string) =>
  api.post(`/sessions/${id}/alignment`).then((r) => r.data)

export const getAudioUrl = (id: string) => `/api/sessions/${id}/audio`

// Screenshots
export const uploadScreenshot = (id: string, blob: Blob) => {
  const form = new FormData()
  form.append('file', blob, 'screenshot.jpg')
  return api.post(`/sessions/${id}/screenshots`, form).then((r) => r.data)
}

export const listScreenshots = (id: string) =>
  api.get<{ screenshots: { filename: string; timestamp: number }[] }>(`/sessions/${id}/screenshots`).then((r) => r.data.screenshots)

export const getScreenshotUrl = (id: string, filename: string) =>
  `/api/sessions/${id}/screenshots/${filename}`

// Notion
export const exportToNotion = (id: string) =>
  api.post<{ notion_page_id: string; url: string }>(`/sessions/${id}/export/notion`).then((r) => r.data)

// Extraction (transcript polish + meeting note)
export const triggerExtract = (id: string) =>
  api.post<ExtractResult>(`/sessions/${id}/extract`).then((r) => r.data)

export const getMeetingNote = (id: string) =>
  api.get<MeetingNote>(`/sessions/${id}/meeting-note`).then((r) => r.data)

export const getPolishedTranscript = (id: string) =>
  api.get<{ session_id: string; transcript: string }>(`/sessions/${id}/polished-transcript`).then((r) => r.data)

// YouTube import
export const importYouTube = (url: string, title?: string) =>
  api.post<SessionInfo>('/youtube/import', { url, title }).then((r) => r.data)

// Config
export const getConfig = () =>
  api.get<AppConfig>('/config').then((r) => r.data)
