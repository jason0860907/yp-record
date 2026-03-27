import type { EnrichedTranscriptSegment } from '../types'

const SPEAKER_COLORS: Record<number, { border: string; badge: string; word: string; active: string }> = {
  0: { border: 'border-l-indigo-400', badge: 'bg-indigo-100/70 text-indigo-600', word: 'hover:bg-indigo-50 text-slate-600', active: 'bg-indigo-100 text-indigo-700 font-semibold' },
  1: { border: 'border-l-emerald-400', badge: 'bg-emerald-100/70 text-emerald-600', word: 'hover:bg-emerald-50 text-slate-600', active: 'bg-emerald-100 text-emerald-700 font-semibold' },
  2: { border: 'border-l-amber-400', badge: 'bg-amber-100/70 text-amber-600', word: 'hover:bg-amber-50 text-slate-600', active: 'bg-amber-100 text-amber-700 font-semibold' },
  3: { border: 'border-l-rose-400', badge: 'bg-rose-100/70 text-rose-600', word: 'hover:bg-rose-50 text-slate-600', active: 'bg-rose-100 text-rose-700 font-semibold' },
  4: { border: 'border-l-violet-400', badge: 'bg-violet-100/70 text-violet-600', word: 'hover:bg-violet-50 text-slate-600', active: 'bg-violet-100 text-violet-700 font-semibold' },
}

// CJK Unified Ideographs + common CJK ranges
const CJK_RE = /[\u2E80-\u9FFF\uF900-\uFAFF\uFE30-\uFE4F]/

function isCJK(text: string): boolean {
  return CJK_RE.test(text)
}

function getSpeakerIndex(speaker: string | null): number {
  if (!speaker) return 0
  const match = speaker.match(/\d+/)
  return match ? parseInt(match[0]) % 5 : 0
}

function formatTs(secs: number): string {
  const m = Math.floor(secs / 60)
  const s = secs % 60
  return `${m}:${s.toFixed(1).padStart(4, '0')}`
}

interface Props {
  segments: EnrichedTranscriptSegment[]
  onSeek?: (time: number) => void
  playingTime?: number
}

export default function WordTimeline({ segments, onSeek, playingTime }: Props) {
  if (segments.length === 0) {
    return <p className="text-sm text-slate-400 py-4">No word-level data available.</p>
  }

  return (
    <div className="space-y-3">
      {segments.map((seg) => {
        const idx = getSpeakerIndex(seg.speaker)
        const colors = SPEAKER_COLORS[idx] ?? SPEAKER_COLORS[0]
        const speakerLabel = seg.speaker ? `S${getSpeakerIndex(seg.speaker)}` : '?'

        return (
          <div key={seg.id} className={`rounded-xl border-l-[3px] ${colors.border} bg-white/40 backdrop-blur-sm border border-white/50 pl-4 pr-4 py-3 shadow-sm`}>
            <div className="flex items-center gap-2.5 mb-2">
              <span className={`rounded-md px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${colors.badge}`}>
                {speakerLabel}
              </span>
              <span className="font-mono text-[10px] text-slate-400">
                {formatTs(seg.start)} - {formatTs(seg.end)}
              </span>
            </div>
            <div className="flex flex-wrap">
              {seg.words.map((w, wi) => {
                const isActive = playingTime !== undefined && playingTime >= w.start && playingTime < w.end
                const cjk = isCJK(w.word)
                const nextWord = seg.words[wi + 1]
                const needsGap = !cjk && nextWord && !isCJK(nextWord.word)
                return (
                  <button
                    key={wi}
                    onClick={() => onSeek?.(w.start)}
                    title={`${formatTs(w.start)}-${formatTs(w.end)}`}
                    className={`rounded-md py-0.5 text-sm transition-all duration-150 cursor-pointer ${
                      cjk ? 'px-0' : 'px-0.5'
                    } ${needsGap ? 'mr-0.5' : ''} ${
                      isActive ? colors.active : colors.word
                    }`}
                  >
                    {w.word}
                  </button>
                )
              })}
            </div>
          </div>
        )
      })}
    </div>
  )
}
