import { useCallback, useRef, useEffect } from 'react'

const TARGET_SAMPLE_RATE = 16000
const CHUNK_INTERVAL_MS = 100

interface UseAudioMergerReturn {
  startMerging: (
    micStream: MediaStream | null,
    tabStream: MediaStream,
    onChunk: (chunk: ArrayBuffer) => void,
    onLevels?: (mic: number, tab: number) => void
  ) => void
  stopMerging: () => void
}

function computeRMS(buffer: Float32Array): number {
  if (buffer.length === 0) return 0
  let sum = 0
  for (let i = 0; i < buffer.length; i++) sum += buffer[i] * buffer[i]
  return Math.min(1, Math.sqrt(sum / buffer.length))
}

function downsampleBuffer(buffer: Float32Array, inputRate: number, outputRate: number): Float32Array {
  if (inputRate === outputRate) return buffer
  const ratio = inputRate / outputRate
  const newLength = Math.round(buffer.length / ratio)
  const result = new Float32Array(newLength)
  for (let i = 0; i < newLength; i++) {
    result[i] = buffer[Math.min(Math.round(i * ratio), buffer.length - 1)]
  }
  return result
}

function floatTo16BitPCM(samples: Float32Array): Int16Array {
  const pcm = new Int16Array(samples.length)
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]))
    pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff
  }
  return pcm
}

function interleaveStereo(left: Float32Array, right: Float32Array): Float32Array {
  const length = Math.min(left.length, right.length)
  const interleaved = new Float32Array(length * 2)
  for (let i = 0; i < length; i++) {
    interleaved[i * 2] = left[i]
    interleaved[i * 2 + 1] = right[i]
  }
  return interleaved
}

export function useAudioMerger(): UseAudioMergerReturn {
  const audioContextRef = useRef<AudioContext | null>(null)
  const micWorkletRef = useRef<AudioWorkletNode | null>(null)
  const tabWorkletRef = useRef<AudioWorkletNode | null>(null)
  const micSourceRef = useRef<MediaStreamAudioSourceNode | null>(null)
  const tabSourceRef = useRef<MediaStreamAudioSourceNode | null>(null)
  const onChunkRef = useRef<((chunk: ArrayBuffer) => void) | null>(null)
  const onLevelsRef = useRef<((mic: number, tab: number) => void) | null>(null)
  const hasMicRef = useRef<boolean>(false)
  const micBufferRef = useRef<Float32Array[]>([])
  const tabBufferRef = useRef<Float32Array[]>([])
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const flushChunks = useCallback((inputSampleRate: number) => {
    const tabBuffers = tabBufferRef.current
    tabBufferRef.current = []

    if (hasMicRef.current) {
      const micBuffers = micBufferRef.current
      micBufferRef.current = []
      if (micBuffers.length === 0 && tabBuffers.length === 0) return

      const micTotal = micBuffers.reduce((s, b) => s + b.length, 0)
      const tabTotal = tabBuffers.reduce((s, b) => s + b.length, 0)
      const totalLength = Math.min(micTotal, tabTotal)
      if (totalLength === 0) return

      const micConcat = new Float32Array(micTotal)
      let off = 0
      for (const b of micBuffers) { micConcat.set(b, off); off += b.length }

      const tabConcat = new Float32Array(tabTotal)
      off = 0
      for (const b of tabBuffers) { tabConcat.set(b, off); off += b.length }

      onLevelsRef.current?.(computeRMS(micConcat), computeRMS(tabConcat))

      const mic16 = downsampleBuffer(micConcat.subarray(0, totalLength), inputSampleRate, TARGET_SAMPLE_RATE)
      const tab16 = downsampleBuffer(tabConcat.subarray(0, totalLength), inputSampleRate, TARGET_SAMPLE_RATE)
      const stereo = interleaveStereo(mic16, tab16)
      onChunkRef.current?.(floatTo16BitPCM(stereo).buffer)
    } else {
      if (tabBuffers.length === 0) return
      const tabTotal = tabBuffers.reduce((s, b) => s + b.length, 0)
      if (tabTotal === 0) return

      const tabConcat = new Float32Array(tabTotal)
      let off = 0
      for (const b of tabBuffers) { tabConcat.set(b, off); off += b.length }

      onLevelsRef.current?.(0, computeRMS(tabConcat))
      const tabDown = downsampleBuffer(tabConcat, inputSampleRate, TARGET_SAMPLE_RATE)
      onChunkRef.current?.(floatTo16BitPCM(tabDown).buffer)
    }
  }, [])

  const startMerging = useCallback(async (
    micStream: MediaStream | null,
    tabStream: MediaStream,
    onChunk: (chunk: ArrayBuffer) => void,
    onLevels?: (mic: number, tab: number) => void
  ) => {
    onChunkRef.current = onChunk
    onLevelsRef.current = onLevels ?? null
    hasMicRef.current = micStream !== null

    const audioContext = new AudioContext()
    audioContextRef.current = audioContext
    const inputSampleRate = audioContext.sampleRate
    const nullSink = audioContext.createMediaStreamDestination()

    try {
      await audioContext.audioWorklet.addModule('/pcm-processor.js')

      const tabSource = audioContext.createMediaStreamSource(tabStream)
      tabSourceRef.current = tabSource
      const tabWorklet = new AudioWorkletNode(audioContext, 'pcm-processor')
      tabWorkletRef.current = tabWorklet
      tabWorklet.port.onmessage = (e: MessageEvent<{ samples: Float32Array }>) => {
        tabBufferRef.current.push(e.data.samples)
      }
      tabSource.connect(tabWorklet)
      tabWorklet.connect(nullSink)

      if (micStream) {
        const micSource = audioContext.createMediaStreamSource(micStream)
        micSourceRef.current = micSource
        const micWorklet = new AudioWorkletNode(audioContext, 'pcm-processor')
        micWorkletRef.current = micWorklet
        micWorklet.port.onmessage = (e: MessageEvent<{ samples: Float32Array }>) => {
          micBufferRef.current.push(e.data.samples)
        }
        micSource.connect(micWorklet)
        micWorklet.connect(nullSink)
      }
    } catch {
      // Fallback: ScriptProcessorNode
      const tabSource = audioContext.createMediaStreamSource(tabStream)
      tabSourceRef.current = tabSource
      const proc = audioContext.createScriptProcessor(4096, 1, 1)
      proc.onaudioprocess = (e) => {
        tabBufferRef.current.push(new Float32Array(e.inputBuffer.getChannelData(0)))
      }
      tabSource.connect(proc)
      proc.connect(nullSink)

      if (micStream) {
        const micSource = audioContext.createMediaStreamSource(micStream)
        micSourceRef.current = micSource
        const micProc = audioContext.createScriptProcessor(4096, 1, 1)
        micProc.onaudioprocess = (e) => {
          micBufferRef.current.push(new Float32Array(e.inputBuffer.getChannelData(0)))
        }
        micSource.connect(micProc)
        micProc.connect(nullSink)
      }
    }

    intervalRef.current = setInterval(() => flushChunks(inputSampleRate), CHUNK_INTERVAL_MS)
  }, [flushChunks])

  const stopMerging = useCallback(() => {
    if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null }
    micWorkletRef.current?.disconnect(); micWorkletRef.current = null
    tabWorkletRef.current?.disconnect(); tabWorkletRef.current = null
    micSourceRef.current?.disconnect(); micSourceRef.current = null
    tabSourceRef.current?.disconnect(); tabSourceRef.current = null
    audioContextRef.current?.close(); audioContextRef.current = null
    micBufferRef.current = []
    tabBufferRef.current = []
    onChunkRef.current = null
    onLevelsRef.current = null
  }, [])

  useEffect(() => () => stopMerging(), [stopMerging])

  return { startMerging, stopMerging }
}
