import { useEffect, useRef, useCallback } from 'react'

declare global {
  interface Window {
    YT: typeof YT
    onYouTubeIframeAPIReady: (() => void) | undefined
  }
}

interface Props {
  videoId: string
  currentTime?: number
  onTimeUpdate?: (t: number) => void
}

let apiLoaded = false
let apiReady = false
const readyCallbacks: (() => void)[] = []

function ensureAPI(cb: () => void) {
  if (apiReady) { cb(); return }
  readyCallbacks.push(cb)
  if (apiLoaded) return
  apiLoaded = true
  const prev = window.onYouTubeIframeAPIReady
  window.onYouTubeIframeAPIReady = () => {
    prev?.()
    apiReady = true
    readyCallbacks.forEach((fn) => fn())
    readyCallbacks.length = 0
  }
  const tag = document.createElement('script')
  tag.src = 'https://www.youtube.com/iframe_api'
  document.head.appendChild(tag)
}

export default function YouTubePlayer({ videoId, currentTime, onTimeUpdate }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const playerRef = useRef<YT.Player | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const onTimeUpdateRef = useRef(onTimeUpdate)
  onTimeUpdateRef.current = onTimeUpdate

  const startPolling = useCallback(() => {
    if (intervalRef.current) return
    intervalRef.current = setInterval(() => {
      const p = playerRef.current
      if (p && typeof p.getCurrentTime === 'function') {
        onTimeUpdateRef.current?.(p.getCurrentTime())
      }
    }, 250)
  }, [])

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
  }, [])

  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    ensureAPI(() => {
      if (playerRef.current) return
      const div = document.createElement('div')
      el.appendChild(div)
      playerRef.current = new window.YT.Player(div, {
        videoId,
        width: '100%',
        height: '100%',
        playerVars: { rel: 0, modestbranding: 1 },
        events: {
          onStateChange: (e: YT.OnStateChangeEvent) => {
            if (e.data === window.YT.PlayerState.PLAYING) {
              startPolling()
            } else {
              stopPolling()
              // Report final time on pause
              if (playerRef.current && typeof playerRef.current.getCurrentTime === 'function') {
                onTimeUpdateRef.current?.(playerRef.current.getCurrentTime())
              }
            }
          },
        },
      })
    })

    return () => {
      stopPolling()
      playerRef.current?.destroy()
      playerRef.current = null
    }
  }, [videoId, startPolling, stopPolling])

  // Seek when currentTime changes (user clicked a word)
  useEffect(() => {
    if (currentTime === undefined) return
    const p = playerRef.current
    if (p && typeof p.seekTo === 'function') {
      p.seekTo(currentTime, true)
    }
  }, [currentTime])

  return (
    <div
      ref={containerRef}
      className="w-full rounded-lg overflow-hidden border border-slate-200/30 aspect-video"
    />
  )
}
