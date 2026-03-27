import { useRef, useCallback } from 'react'
import { uploadScreenshot } from '../api/client'

export function useScreenshotCapture() {
  const intervalRef = useRef<number | null>(null)
  const videoRef = useRef<HTMLVideoElement | null>(null)

  const start = useCallback((
    sessionId: string,
    intervalSeconds: number,
    displayStream: MediaStream,
  ) => {
    const video = document.createElement('video')
    video.muted = true
    video.srcObject = displayStream
    video.play()
    videoRef.current = video

    const captureFrame = () => {
      const v = videoRef.current
      if (!v || v.readyState < 2) return
      const canvas = document.createElement('canvas')
      canvas.width = v.videoWidth
      canvas.height = v.videoHeight
      canvas.getContext('2d')?.drawImage(v, 0, 0)
      canvas.toBlob((blob) => {
        if (blob) uploadScreenshot(sessionId, blob).catch(console.error)
      }, 'image/jpeg', 0.75)
    }

    window.setTimeout(captureFrame, 1000)
    intervalRef.current = window.setInterval(captureFrame, intervalSeconds * 1000)
  }, [])

  const stop = useCallback(() => {
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    videoRef.current = null
  }, [])

  return { startScreenshot: start, stopScreenshot: stop }
}
