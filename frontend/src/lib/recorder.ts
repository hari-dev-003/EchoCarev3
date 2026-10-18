import { useRef, useState } from 'react'

/** Records microphone audio and encodes it as 16-bit PCM WAV (the format Gemini transcription accepts reliably). */
export function useRecorder(onDone: (wav: Blob) => void) {
  const [recording, setRecording] = useState(false)
  const ctx = useRef<AudioContext | null>(null); const chunks = useRef<Float32Array[]>([]); const stream = useRef<MediaStream | null>(null); const proc = useRef<ScriptProcessorNode | null>(null)
  const supported = typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia
  const start = async () => {
    try {
      stream.current = await navigator.mediaDevices.getUserMedia({ audio: true })
      const ac = new AudioContext(); ctx.current = ac; chunks.current = []
      const src = ac.createMediaStreamSource(stream.current); const p = ac.createScriptProcessor(4096, 1, 1); proc.current = p
      p.onaudioprocess = e => chunks.current.push(new Float32Array(e.inputBuffer.getChannelData(0)))
      src.connect(p); p.connect(ac.destination); setRecording(true)
    } catch { alert('Microphone permission was denied or is unavailable.') }
  }
  const stop = () => {
    const ac = ctx.current; if (!ac) return
    proc.current?.disconnect(); stream.current?.getTracks().forEach(t => t.stop()); setRecording(false)
    const len = chunks.current.reduce((a, c) => a + c.length, 0); const data = new Float32Array(len); let o = 0; chunks.current.forEach(c => { data.set(c, o); o += c.length })
    onDone(encodeWav(data, ac.sampleRate)); ac.close()
  }
  return { recording, start, stop, supported }
}

function encodeWav(samples: Float32Array, rate: number): Blob {
  const buf = new ArrayBuffer(44 + samples.length * 2); const v = new DataView(buf)
  const w = (o: number, s: string) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)) }
  w(0, 'RIFF'); v.setUint32(4, 36 + samples.length * 2, true); w(8, 'WAVE'); w(12, 'fmt '); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true)
  v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true); w(36, 'data'); v.setUint32(40, samples.length * 2, true)
  for (let i = 0; i < samples.length; i++) { const s = Math.max(-1, Math.min(1, samples[i])); v.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true) }
  return new Blob([buf], { type: 'audio/wav' })
}
