import { useState, useRef, useEffect } from 'react'
import { Play, Pause } from 'lucide-react'
import { formatTime } from '../utils/formatters'

interface Props {
  src: string
  currentTime?: number
  onTimeUpdate?: (t: number) => void
}

export default function AudioPlayer({ src, currentTime, onTimeUpdate }: Props) {
  const audioRef = useRef<HTMLAudioElement>(null)
  const [playing, setPlaying] = useState(false)
  const [duration, setDuration] = useState(0)
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return
    const onLoaded = () => setDuration(audio.duration)
    const onTime = () => {
      setElapsed(audio.currentTime)
      onTimeUpdate?.(audio.currentTime)
    }
    const onEnded = () => setPlaying(false)
    audio.addEventListener('loadedmetadata', onLoaded)
    audio.addEventListener('timeupdate', onTime)
    audio.addEventListener('ended', onEnded)
    return () => {
      audio.removeEventListener('loadedmetadata', onLoaded)
      audio.removeEventListener('timeupdate', onTime)
      audio.removeEventListener('ended', onEnded)
    }
  }, [onTimeUpdate])

  useEffect(() => {
    if (audioRef.current && currentTime !== undefined) {
      audioRef.current.currentTime = currentTime
    }
  }, [currentTime])

  const togglePlay = () => {
    const audio = audioRef.current
    if (!audio) return
    if (playing) {
      audio.pause()
      setPlaying(false)
    } else {
      audio.play()
      setPlaying(true)
    }
  }

  const seek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const t = parseFloat(e.target.value)
    if (audioRef.current) audioRef.current.currentTime = t
    setElapsed(t)
  }

  const progress = duration > 0 ? (elapsed / duration) * 100 : 0

  return (
    <div className="flex items-center gap-4 rounded-2xl bg-white/40 backdrop-blur-lg border border-white/50 px-5 py-4 shadow-sm">
      <audio ref={audioRef} src={src} preload="metadata" />

      <button
        onClick={togglePlay}
        className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-accent text-white hover:bg-accent-dark transition-all duration-200 cursor-pointer shadow-sm"
      >
        {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4 ml-0.5" />}
      </button>

      <div className="flex-1 flex flex-col gap-1.5">
        <div className="relative h-1.5 w-full rounded-full bg-slate-200/60 overflow-hidden">
          <div
            className="absolute inset-y-0 left-0 rounded-full bg-accent transition-all duration-75"
            style={{ width: `${progress}%` }}
          />
          <input
            type="range"
            min={0}
            max={duration || 0}
            step={0.1}
            value={elapsed}
            onChange={seek}
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          />
        </div>
        <div className="flex justify-between">
          <span className="text-[10px] font-mono text-slate-400">{formatTime(elapsed)}</span>
          <span className="text-[10px] font-mono text-slate-400">{formatTime(duration)}</span>
        </div>
      </div>
    </div>
  )
}
