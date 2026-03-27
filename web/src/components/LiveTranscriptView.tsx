import { useEffect, useRef, useState, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Mic, ArrowDown } from 'lucide-react'
import { useStore } from '../store/useStore'
import { getSessionSegments } from '../api/client'
import SegmentBubble from './SegmentBubble'

interface Props {
  sessionId?: string | null
}

export default function LiveTranscriptView({ sessionId }: Props) {
  const activeSession = useStore((s) => s.activeSession)
  const liveSegments = useStore((s) => s.segments)
  const bottomRef = useRef<HTMLDivElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const userScrolledUp = useRef(false)
  const [hasNewBelow, setHasNewBelow] = useState(false)

  const isPastSession = !!sessionId && sessionId !== activeSession?.id

  const { data: historicalSegments } = useQuery({
    queryKey: ['segments', sessionId],
    queryFn: () => getSessionSegments(sessionId!),
    enabled: isPastSession,
  })

  const segments = isPastSession ? (historicalSegments ?? []) : liveSegments

  const handleScroll = useCallback(() => {
    const el = scrollRef.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 60
    userScrolledUp.current = !atBottom
    if (atBottom) setHasNewBelow(false)
  }, [])

  const scrollToBottom = useCallback(() => {
    userScrolledUp.current = false
    setHasNewBelow(false)
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => {
    if (userScrolledUp.current) {
      setHasNewBelow(true)
    } else {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [segments.length])

  if (segments.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 text-slate-400">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-accent/[0.06]">
          <Mic className="h-7 w-7 text-accent/30" />
        </div>
        <p className="text-sm">
          {isPastSession
            ? 'No transcript saved for this session'
            : 'Start recording to see live transcript'}
        </p>
      </div>
    )
  }

  return (
    <div
      ref={scrollRef}
      onScroll={handleScroll}
      className="h-full overflow-y-auto px-5 py-4 space-y-2 scrollbar-thin"
    >
      {segments.map((seg) => (
        <SegmentBubble key={seg.id} segment={seg} />
      ))}
      <div ref={bottomRef} />

      {hasNewBelow && (
        <div className="sticky bottom-3 flex justify-center pointer-events-none">
          <button
            onClick={scrollToBottom}
            className="pointer-events-auto flex items-center gap-1.5 rounded-full bg-accent px-4 py-2 text-xs font-medium text-white shadow-md hover:bg-accent-dark transition-all duration-200 cursor-pointer"
          >
            <ArrowDown className="h-3 w-3" />
            New segments
          </button>
        </div>
      )}
    </div>
  )
}
