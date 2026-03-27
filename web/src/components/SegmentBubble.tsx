import type { TranscriptSegment } from '../types'
import { formatTime } from '../utils/formatters'

interface Props {
  segment: TranscriptSegment
}

export default function SegmentBubble({ segment }: Props) {
  const isSelf = segment.channel === 0
  const label = isSelf ? 'Mic' : 'Tab'

  const bubbleClass = isSelf
    ? 'bg-indigo-50/70 border-indigo-200/40'
    : 'bg-emerald-50/70 border-emerald-200/40'

  const labelClass = isSelf ? 'text-indigo-500' : 'text-emerald-600'

  return (
    <div className={`rounded-xl border px-4 py-2.5 backdrop-blur-sm ${bubbleClass}`}>
      <div className="flex items-baseline gap-2">
        <span className={`text-[10px] font-semibold uppercase tracking-wider ${labelClass}`}>{label}</span>
        {segment.start_time > 0 && (
          <span className="text-[10px] font-mono text-slate-400">{formatTime(segment.start_time)}</span>
        )}
      </div>
      <p className="text-sm text-slate-700 leading-relaxed mt-0.5">{segment.text}</p>
    </div>
  )
}
