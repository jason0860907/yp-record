/**
 * AudioWorklet processor for PCM audio capture.
 *
 * Runs on a dedicated audio thread — avoids main-thread jank that
 * ScriptProcessorNode causes during long meetings.
 *
 * Receives audio from one input channel and buffers Float32 samples.
 * Every FLUSH_INTERVAL_FRAMES frames (~100ms at 48kHz), sends the
 * buffered data to the main thread via port.postMessage.
 */

const FLUSH_INTERVAL_FRAMES = 128 * 37 // ~4736 frames ≈ 98.7ms at 48kHz

class PCMProcessor extends AudioWorkletProcessor {
  constructor() {
    super()
    this._buffer = []
    this._frameCount = 0
  }

  process(inputs) {
    const input = inputs[0]
    if (!input || input.length === 0) return true

    // Copy channel 0 data
    const channelData = input[0]
    if (channelData && channelData.length > 0) {
      this._buffer.push(new Float32Array(channelData))
      this._frameCount += channelData.length
    }

    if (this._frameCount >= FLUSH_INTERVAL_FRAMES) {
      // Concatenate buffered samples
      const total = this._buffer.reduce((sum, b) => sum + b.length, 0)
      const merged = new Float32Array(total)
      let offset = 0
      for (const buf of this._buffer) {
        merged.set(buf, offset)
        offset += buf.length
      }

      this.port.postMessage({ samples: merged }, [merged.buffer])

      this._buffer = []
      this._frameCount = 0
    }

    return true
  }
}

registerProcessor('pcm-processor', PCMProcessor)
