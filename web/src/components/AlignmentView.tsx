import { useState, useMemo, useCallback, useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Crop, RotateCcw } from 'lucide-react'
import { getAlignmentStatus, getAlignmentResult, getAudioUrl, getSession, listScreenshots, getScreenshotUrl } from '../api/client'
import { useStore } from '../store/useStore'
import AlignmentStatusBanner from './AlignmentStatusBanner'
import WordTimeline from './WordTimeline'
import AudioPlayer from './AudioPlayer'
import YouTubePlayer from './YouTubePlayer'
import type { AlignmentStatus } from '../types'

function extractYouTubeId(url: string): string | null {
  try {
    const u = new URL(url)
    if (u.hostname.includes('youtu.be')) return u.pathname.slice(1)
    return u.searchParams.get('v')
  } catch {
    return null
  }
}

interface CropRect {
  x: number; y: number; w: number; h: number  // 0-1 percentages
}

interface Props {
  sessionId: string
}

/**
 * Draw cropped region of src image onto a canvas, centered with padding.
 * Canvas keeps the same aspect ratio as the original image.
 */
function drawCropped(
  canvas: HTMLCanvasElement,
  img: HTMLImageElement,
  crop: CropRect,
  padding: number = 0.03, // 3% of canvas dimension as padding
) {
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  // Source rectangle in pixels
  const sx = crop.x * img.naturalWidth
  const sy = crop.y * img.naturalHeight
  const sw = crop.w * img.naturalWidth
  const sh = crop.h * img.naturalHeight

  // Canvas = same size as original image
  canvas.width = img.naturalWidth
  canvas.height = img.naturalHeight

  // Fill background
  ctx.fillStyle = '#0a0a0a'
  ctx.fillRect(0, 0, canvas.width, canvas.height)

  // Padding in pixels
  const padX = canvas.width * padding
  const padY = canvas.height * padding
  const availW = canvas.width - padX * 2
  const availH = canvas.height - padY * 2

  // Scale crop to fit inside available area, preserving aspect ratio
  const scale = Math.min(availW / sw, availH / sh)
  const dw = sw * scale
  const dh = sh * scale

  // Center
  const dx = (canvas.width - dw) / 2
  const dy = (canvas.height - dh) / 2

  ctx.drawImage(img, sx, sy, sw, sh, dx, dy, dw, dh)
}

export default function AlignmentView({ sessionId }: Props) {
  const [seekTime, setSeekTime] = useState<number | undefined>()
  const [playingTime, setPlayingTime] = useState<number>(0)
  const [cropRect, setCropRect] = useState<CropRect | null>(null)
  const [isCropping, setIsCropping] = useState(false)
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null)
  const [dragEnd, setDragEnd] = useState<{ x: number; y: number } | null>(null)
  const [croppedDataUrl, setCroppedDataUrl] = useState<string | null>(null)
  const imgRef = useRef<HTMLImageElement>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  // Determine if this is a YouTube session
  const activeSession = useStore((s) => s.activeSession)
  const { data: fetchedSession } = useQuery({
    queryKey: ['session', sessionId],
    queryFn: () => getSession(sessionId),
    enabled: activeSession?.id !== sessionId,
  })
  const session = activeSession?.id === sessionId ? activeSession : fetchedSession
  const youtubeVideoId = session?.source === 'youtube' && session.source_url
    ? extractYouTubeId(session.source_url)
    : null

  const { data: status } = useQuery<AlignmentStatus>({
    queryKey: ['alignment-status', sessionId],
    queryFn: () => getAlignmentStatus(sessionId),
    refetchInterval: (query) => {
      const s = query.state.data?.status
      return s === 'processing' ? 2000 : false
    },
  })

  const { data: result } = useQuery({
    queryKey: ['alignment', sessionId],
    queryFn: () => getAlignmentResult(sessionId),
    enabled: status?.status === 'completed',
  })

  const { data: screenshots } = useQuery({
    queryKey: ['screenshots', sessionId],
    queryFn: () => listScreenshots(sessionId),
  })

  const currentScreenshot = useMemo(() => {
    if (!screenshots || screenshots.length === 0) return null
    let best = screenshots[0]
    for (const s of screenshots) {
      if (s.timestamp <= playingTime) best = s
      else break
    }
    return best
  }, [screenshots, playingTime])

  const currentSrc = currentScreenshot
    ? getScreenshotUrl(sessionId, currentScreenshot.filename)
    : null

  // When crop or current screenshot changes, render cropped version
  useEffect(() => {
    if (!cropRect || !currentSrc) {
      setCroppedDataUrl(null)
      return
    }
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => {
      if (!canvasRef.current) canvasRef.current = document.createElement('canvas')
      drawCropped(canvasRef.current, img, cropRect)
      setCroppedDataUrl(canvasRef.current.toDataURL('image/jpeg', 0.9))
    }
    img.src = currentSrc
  }, [cropRect, currentSrc])

  // Mouse → image percentage
  const toImgPercent = useCallback((e: React.MouseEvent) => {
    const img = imgRef.current
    if (!img) return { x: 0, y: 0 }
    const rect = img.getBoundingClientRect()
    return {
      x: Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width)),
      y: Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height)),
    }
  }, [])

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (!isCropping) return
    e.preventDefault()
    setDragStart(toImgPercent(e))
    setDragEnd(null)
  }, [isCropping, toImgPercent])

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isCropping || !dragStart) return
    setDragEnd(toImgPercent(e))
  }, [isCropping, dragStart, toImgPercent])

  const handleMouseUp = useCallback(() => {
    if (!isCropping || !dragStart || !dragEnd) return
    const x = Math.min(dragStart.x, dragEnd.x)
    const y = Math.min(dragStart.y, dragEnd.y)
    const w = Math.abs(dragEnd.x - dragStart.x)
    const h = Math.abs(dragEnd.y - dragStart.y)
    if (w > 0.02 && h > 0.02) {
      setCropRect({ x, y, w, h })
    }
    setIsCropping(false)
    setDragStart(null)
    setDragEnd(null)
  }, [isCropping, dragStart, dragEnd])

  const selectionStyle = useMemo(() => {
    if (!dragStart || !dragEnd) return null
    return {
      left: `${Math.min(dragStart.x, dragEnd.x) * 100}%`,
      top: `${Math.min(dragStart.y, dragEnd.y) * 100}%`,
      width: `${Math.abs(dragEnd.x - dragStart.x) * 100}%`,
      height: `${Math.abs(dragEnd.y - dragStart.y) * 100}%`,
    }
  }, [dragStart, dragEnd])

  const showBanner = !status || ['not_started', 'processing', 'failed'].includes(status.status)
  const hasScreenshots = screenshots && screenshots.length > 0

  // Which image to display: cropped canvas or original
  const displaySrc = (cropRect && !isCropping && croppedDataUrl) ? croppedDataUrl : currentSrc

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Top: banner + player */}
      <div className="flex-shrink-0 px-5 pt-5 space-y-4">
        {showBanner && (
          <AlignmentStatusBanner
            sessionId={sessionId}
            status={status ?? null}
            serviceAvailable={status?.service_available ?? false}
          />
        )}
        {!youtubeVideoId && status?.wav_available && (
          <AudioPlayer
            src={getAudioUrl(sessionId)}
            currentTime={seekTime}
            onTimeUpdate={setPlayingTime}
          />
        )}
      </div>

      {/* Main: left media (60%) + word timeline (right 40%) */}
      <div className={`flex-1 min-h-0 flex ${(hasScreenshots || youtubeVideoId) ? 'gap-4' : ''} px-5 py-4`}>
        {/* Left: YouTube embed OR screenshot */}
        {youtubeVideoId ? (
          <div className="w-3/5 flex-shrink-0 flex items-start">
            <YouTubePlayer
              videoId={youtubeVideoId}
              currentTime={seekTime}
              onTimeUpdate={setPlayingTime}
            />
          </div>
        ) : currentScreenshot && currentSrc ? (
          <div className="w-3/5 flex-shrink-0">
            <div
              className={`relative rounded-lg border border-white/[0.08] bg-black/20 overflow-hidden select-none ${isCropping ? 'cursor-crosshair' : ''}`}
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
            >
              {isCropping ? (
                <img
                  ref={imgRef}
                  src={currentSrc}
                  alt="Select crop area"
                  className="w-full h-auto"
                  draggable={false}
                />
              ) : (
                <img
                  src={displaySrc!}
                  alt={`Screenshot at ${Math.floor(currentScreenshot.timestamp)}s`}
                  className="w-full h-auto"
                  draggable={false}
                />
              )}

              {isCropping && selectionStyle && (
                <div
                  className="absolute border-2 border-accent bg-accent/10 rounded-sm pointer-events-none"
                  style={selectionStyle}
                />
              )}

              <div className="absolute bottom-2 left-2 flex items-center gap-1">
                {!isCropping && !cropRect && (
                  <button
                    onClick={(e) => { e.stopPropagation(); setIsCropping(true) }}
                    className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-white/70 bg-black/50 hover:bg-black/70 hover:text-white transition-colors cursor-pointer backdrop-blur-sm"
                  >
                    <Crop className="h-3 w-3" />
                    Crop
                  </button>
                )}
                {isCropping && (
                  <span className="rounded-md px-2 py-1 text-xs text-white/70 bg-black/50 backdrop-blur-sm">
                    Drag to select area
                  </span>
                )}
                {cropRect && !isCropping && (
                  <>
                    <button
                      onClick={(e) => { e.stopPropagation(); setIsCropping(true) }}
                      className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-white/70 bg-black/50 hover:bg-black/70 hover:text-white transition-colors cursor-pointer backdrop-blur-sm"
                    >
                      <Crop className="h-3 w-3" />
                      Re-crop
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); setCropRect(null); setCroppedDataUrl(null) }}
                      className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-white/70 bg-black/50 hover:bg-black/70 hover:text-white transition-colors cursor-pointer backdrop-blur-sm"
                    >
                      <RotateCcw className="h-3 w-3" />
                      Reset
                    </button>
                  </>
                )}
              </div>
            </div>
          </div>
        ) : null}

        {/* Right: word timeline */}
        <div className={`${(hasScreenshots || youtubeVideoId) ? 'w-2/5' : 'w-full'} overflow-y-auto scrollbar-thin`}>
          {result && result.segments.length > 0 && (
            <WordTimeline
              segments={result.segments}
              onSeek={(t) => setSeekTime(t)}
              playingTime={playingTime}
            />
          )}
        </div>
      </div>
    </div>
  )
}
