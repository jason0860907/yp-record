import { useState, useCallback, useRef, useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useStore } from '../store/useStore'
import type { TranscriptSegment } from '../types'

interface UseTranscriptStreamReturn {
  connected: boolean
  reconnecting: boolean
  connect: (sessionId: string) => void
  disconnect: () => void
}

const RECONNECT_BASE_DELAY_MS = 1000
const RECONNECT_MAX_DELAY_MS = 30000
const MAX_RECONNECT_ATTEMPTS = 10

export function useTranscriptStream(): UseTranscriptStreamReturn {
  const [connected, setConnected] = useState(false)
  const [reconnecting, setReconnecting] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectAttemptRef = useRef(0)
  const sessionIdRef = useRef<string | null>(null)
  const intentionalCloseRef = useRef(false)
  const queryClient = useQueryClient()

  const addSegment = useStore((s) => s.addSegment)
  const setActiveTab = useStore((s) => s.setActiveTab)
  const setConnectedStore = useStore((s) => s.setConnected)

  const handleMessage = useCallback(
    (event: MessageEvent) => {
      try {
        const msg = JSON.parse(event.data as string) as { type: string; [key: string]: unknown }

        switch (msg.type) {
          case 'transcript_segment':
            addSegment(msg.segment as TranscriptSegment)
            break
          case 'alignment_completed':
          case 'alignment_failed':
            // Invalidate alignment queries so UI refreshes
            queryClient.invalidateQueries({ queryKey: ['alignment'] })
            queryClient.invalidateQueries({ queryKey: ['alignment-status'] })
            if (msg.type === 'alignment_completed') {
              setActiveTab('alignment')
            }
            break
          case 'alignment_started':
            queryClient.invalidateQueries({ queryKey: ['alignment-status'] })
            break
          case 'ping':
            break
          default:
            break
        }
      } catch {
        // ignore parse errors
      }
    },
    [addSegment, queryClient, setActiveTab]
  )

  const connectWs = useCallback(
    (sessionId: string) => {
      if (wsRef.current) wsRef.current.close()

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${protocol}//${window.location.host}/api/transcript/ws?session_id=${sessionId}`
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        setConnected(true)
        setReconnecting(false)
        setConnectedStore(true)
        reconnectAttemptRef.current = 0
      }

      ws.onmessage = handleMessage

      ws.onclose = () => {
        setConnected(false)
        setConnectedStore(false)
        if (!intentionalCloseRef.current && sessionIdRef.current) {
          const attempt = reconnectAttemptRef.current
          if (attempt < MAX_RECONNECT_ATTEMPTS) {
            const delay = Math.min(RECONNECT_BASE_DELAY_MS * Math.pow(2, attempt), RECONNECT_MAX_DELAY_MS)
            setReconnecting(true)
            reconnectTimeoutRef.current = setTimeout(() => {
              reconnectAttemptRef.current = attempt + 1
              if (sessionIdRef.current) connectWs(sessionIdRef.current)
            }, delay)
          } else {
            setReconnecting(false)
          }
        }
      }

      ws.onerror = () => {
        // handled by onclose
      }
    },
    [handleMessage, setConnectedStore]
  )

  const connect = useCallback(
    (sessionId: string) => {
      intentionalCloseRef.current = false
      sessionIdRef.current = sessionId
      reconnectAttemptRef.current = 0
      connectWs(sessionId)
    },
    [connectWs]
  )

  const disconnect = useCallback(() => {
    intentionalCloseRef.current = true
    sessionIdRef.current = null
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    wsRef.current?.close()
    wsRef.current = null
    setConnected(false)
    setReconnecting(false)
    setConnectedStore(false)
  }, [setConnectedStore])

  useEffect(() => () => disconnect(), [disconnect])

  return { connected, reconnecting, connect, disconnect }
}
