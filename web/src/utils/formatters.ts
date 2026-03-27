/** Format seconds as M:SS (e.g. 3:07) */
export function formatTime(secs: number): string {
  const m = Math.floor(secs / 60)
  const s = Math.floor(secs % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

/** Format seconds as M:SS.s with decimal (e.g. 3:07.2) */
export function formatTimestamp(secs: number): string {
  const m = Math.floor(secs / 60)
  const s = secs % 60
  return `${m}:${s.toFixed(1).padStart(4, '0')}`
}
