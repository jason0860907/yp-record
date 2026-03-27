import { useState, useCallback, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useStore } from '../store/useStore'
import { createSession as apiCreateSession, sessionAction, getConfig } from '../api/client'
import { useAudioCapture } from './useAudioCapture'
import { useAudioMerger } from './useAudioMerger'
import { useTranscriptStream } from './useTranscriptStream'
import { useScreenshotCapture } from './useScreenshotCapture'
import type { SessionInfo } from '../types'

interface UseSessionReturn {
  session: SessionInfo | null
  isRecording: boolean
  isCapturing: boolean
  captureError: string | null
  createSession: (title?: string, participants?: string[]) => Promise<void>
  startSession: () => Promise<void>
  pauseSession: () => Promise<void>
  resumeSession: () => Promise<void>
  endSession: () => Promise<void>
}

export function useSession(): UseSessionReturn {
  const [isRecording, setIsRecording] = useState(false)
  const queryClient = useQueryClient()

  const activeSession = useStore((s) => s.activeSession)
  const setActiveSession = useStore((s) => s.setActiveSession)
  const clearSession = useStore((s) => s.clearSession)
  const micEnabled = useStore((s) => s.micEnabled)
  const setAudioLevels = useStore((s) => s.setAudioLevels)

  const audioWsRef = useRef<WebSocket | null>(null)

  const { micStream, tabStream, isCapturing, error: captureError, startCapture, stopCapture } = useAudioCapture()
  const { startMerging, stopMerging } = useAudioMerger()
  const { connect: connectTranscript, disconnect: disconnectTranscript } = useTranscriptStream()
  const { startScreenshot, stopScreenshot } = useScreenshotCapture()

  const connectAudioWs = useCallback((sessionId: string, channels: number) => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/api/audio/ws?session_id=${sessionId}&channels=${channels}`
    const ws = new WebSocket(wsUrl)
    ws.binaryType = 'arraybuffer'
    audioWsRef.current = ws
    return ws
  }, [])

  const disconnectAudioWs = useCallback(() => {
    audioWsRef.current?.close()
    audioWsRef.current = null
  }, [])

  const createSession = useCallback(async (title?: string, participants?: string[]) => {
    clearSession()
    const session = await apiCreateSession(title, participants)
    setActiveSession(session as SessionInfo)
  }, [setActiveSession, clearSession])

  const startSession = useCallback(async () => {
    if (!activeSession) throw new Error('No session. Create one first.')

    try {
      const captured = await startCapture(micEnabled)
      const updatedSession = await sessionAction(activeSession.id, 'start')
      setActiveSession(updatedSession as SessionInfo)

      connectTranscript(activeSession.id)

      const channels = micEnabled ? 2 : 1
      const audioWs = connectAudioWs(activeSession.id, channels)

      audioWs.addEventListener('open', () => {
        startMerging(
          captured.micStream,
          captured.tabStream,
          (chunk: ArrayBuffer) => {
            if (audioWsRef.current?.readyState === WebSocket.OPEN) {
              audioWsRef.current.send(chunk)
            }
          },
          setAudioLevels
        )
      })

      // Start screenshot capture using the display stream
      try {
        const config = await getConfig()
        const interval = config.screenshot_interval_seconds || 10
        startScreenshot(activeSession.id, interval, captured.displayStream)
      } catch { /* screenshot is optional */ }

      setIsRecording(true)
    } catch (err) {
      stopCapture()
      disconnectAudioWs()
      disconnectTranscript()
      throw err
    }
  }, [
    activeSession, micEnabled, startCapture, stopCapture, startMerging,
    connectTranscript, disconnectTranscript, connectAudioWs, disconnectAudioWs,
    setActiveSession, setAudioLevels, startScreenshot,
  ])

  const pauseSession = useCallback(async () => {
    if (!activeSession) return
    stopMerging()
    stopScreenshot()
    disconnectAudioWs()
    const updatedSession = await sessionAction(activeSession.id, 'pause')
    setActiveSession(updatedSession as SessionInfo)
    setIsRecording(false)
  }, [activeSession, setActiveSession, stopMerging, stopScreenshot, disconnectAudioWs])

  const resumeSession = useCallback(async () => {
    if (!activeSession) return
    const updatedSession = await sessionAction(activeSession.id, 'resume')
    setActiveSession(updatedSession as SessionInfo)

    const mic = micStream
    const tab = tabStream
    if (!tab) throw new Error('Tab stream lost. Please restart.')

    const channels = mic ? 2 : 1
    const audioWs = connectAudioWs(activeSession.id, channels)

    audioWs.addEventListener('open', () => {
      startMerging(
        mic,
        tab,
        (chunk: ArrayBuffer) => {
          if (audioWsRef.current?.readyState === WebSocket.OPEN) {
            audioWsRef.current.send(chunk)
          }
        },
        setAudioLevels
      )
    })

    setIsRecording(true)
  }, [activeSession, micStream, tabStream, setActiveSession, startMerging, connectAudioWs, setAudioLevels])

  const endSession = useCallback(async () => {
    if (!activeSession) return
    stopMerging()
    stopScreenshot()
    stopCapture()
    disconnectAudioWs()
    disconnectTranscript()

    const updatedSession = await sessionAction(activeSession.id, 'end')
    setActiveSession(updatedSession as SessionInfo)
    setIsRecording(false)
    queryClient.invalidateQueries({ queryKey: ['sessions'] })
  }, [
    activeSession, queryClient, setActiveSession,
    stopMerging, stopScreenshot, stopCapture, disconnectAudioWs, disconnectTranscript,
  ])

  return {
    session: activeSession,
    isRecording,
    isCapturing,
    captureError,
    createSession,
    startSession,
    pauseSession,
    resumeSession,
    endSession,
  }
}
