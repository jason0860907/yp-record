import { useState, useCallback, useRef, useEffect } from 'react'

interface CaptureResult {
  micStream: MediaStream | null
  tabStream: MediaStream
  displayStream: MediaStream
}

interface UseAudioCaptureReturn {
  micStream: MediaStream | null
  tabStream: MediaStream | null
  isCapturing: boolean
  error: string | null
  startCapture: (micEnabled?: boolean) => Promise<CaptureResult>
  stopCapture: () => void
}

export function useAudioCapture(): UseAudioCaptureReturn {
  const [micStream, setMicStream] = useState<MediaStream | null>(null)
  const [tabStream, setTabStream] = useState<MediaStream | null>(null)
  const [isCapturing, setIsCapturing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const micStreamRef = useRef<MediaStream | null>(null)
  const tabStreamRef = useRef<MediaStream | null>(null)
  const displayStreamRef = useRef<MediaStream | null>(null)

  const stopCapture = useCallback(() => {
    micStreamRef.current?.getTracks().forEach((t) => t.stop())
    micStreamRef.current = null
    setMicStream(null)

    tabStreamRef.current?.getTracks().forEach((t) => t.stop())
    tabStreamRef.current = null
    setTabStream(null)

    displayStreamRef.current?.getTracks().forEach((t) => t.stop())
    displayStreamRef.current = null

    setIsCapturing(false)
  }, [])

  const startCapture = useCallback(async (micEnabled: boolean = true): Promise<CaptureResult> => {
    setError(null)

    try {
      const displayStream = await navigator.mediaDevices.getDisplayMedia({
        audio: { suppressLocalAudioPlayback: false } as MediaTrackConstraints,
        video: { displaySurface: 'browser' },
        selfBrowserSurface: 'include',
      } as DisplayMediaStreamOptions)

      const tabAudioTracks = displayStream.getAudioTracks()
      if (tabAudioTracks.length === 0) {
        displayStream.getTracks().forEach((t) => t.stop())
        const msg = 'No audio track captured from tab. Please select a tab with audio.'
        setError(msg)
        throw new Error(msg)
      }

      displayStreamRef.current = displayStream
      const tabAudioStream = new MediaStream(tabAudioTracks)
      tabStreamRef.current = tabAudioStream
      setTabStream(tabAudioStream)

      tabAudioTracks[0].addEventListener('ended', () => stopCapture())
    } catch (err) {
      if (err instanceof DOMException && err.name === 'NotAllowedError') {
        const msg = 'Tab audio capture was denied. Please allow screen sharing with audio.'
        setError(msg)
        throw new Error(msg)
      }
      const msg = `Failed to capture tab audio: ${err instanceof Error ? err.message : String(err)}`
      setError(msg)
      throw new Error(msg)
    }

    if (micEnabled) {
      try {
        const microphoneStream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        })
        micStreamRef.current = microphoneStream
        setMicStream(microphoneStream)
      } catch (err) {
        tabStreamRef.current?.getTracks().forEach((t) => t.stop())
        tabStreamRef.current = null
        setTabStream(null)
        const msg = `Failed to capture microphone: ${err instanceof Error ? err.message : String(err)}`
        setError(msg)
        throw new Error(msg)
      }
    }

    setIsCapturing(true)
    return { micStream: micStreamRef.current, tabStream: tabStreamRef.current!, displayStream: displayStreamRef.current! }
  }, [stopCapture])

  useEffect(() => {
    return () => {
      micStreamRef.current?.getTracks().forEach((t) => t.stop())
      tabStreamRef.current?.getTracks().forEach((t) => t.stop())
      displayStreamRef.current?.getTracks().forEach((t) => t.stop())
    }
  }, [])

  return { micStream, tabStream, isCapturing, error, startCapture, stopCapture }
}
