// Browser speech: Web Speech API for listening, the interviewer's voice from the backend's
// Featherless TTS proxy (TtsPlayer; the browser voice is the fallback), Web Audio for the
// level the orb follows (mic while listening, playback while speaking). Nothing is
// recorded or uploaded by this code; Chrome's speech recognition itself may send audio to
// Google, which the consent text says. Ported from showcase/components/interview/speech.ts.

type RecognitionResult = { isFinal: boolean; 0: { transcript: string } };

export type Recognition = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((e: { resultIndex: number; results: ArrayLike<RecognitionResult> }) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
};

export function recognitionSupported(): boolean {
  if (typeof window === "undefined") return false;
  const w = window as unknown as Record<string, unknown>;
  return Boolean(w.SpeechRecognition || w.webkitSpeechRecognition);
}

export function createRecognition(): Recognition | null {
  const w = window as unknown as Record<string, new () => Recognition>;
  const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition;
  if (!Ctor) return null;
  const r = new Ctor();
  r.lang = "en-US";
  r.continuous = true;
  r.interimResults = true;
  return r;
}

// Prefer the smoother network voices when the browser offers them.
const PREFERRED = ["Google UK English Female", "Google US English", "Samantha", "Microsoft Aria", "Microsoft Jenny"];

function pickVoice(): SpeechSynthesisVoice | null {
  const voices = window.speechSynthesis.getVoices().filter((v) => v.lang.startsWith("en"));
  for (const name of PREFERRED) {
    const v = voices.find((x) => x.name.startsWith(name));
    if (v) return v;
  }
  return voices[0] ?? null;
}

export function ttsSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

/**
 * Speak `text`; resolves when done or cancelled. `onWord` fires on each word
 * boundary so the blob can pulse with the speech.
 */
export function speak(text: string, onWord: () => void): { done: Promise<void>; cancel: () => void } {
  const synth = window.speechSynthesis;
  synth.cancel();
  const u = new SpeechSynthesisUtterance(text);
  const voice = pickVoice();
  if (voice) u.voice = voice;
  u.rate = 1.02;
  u.pitch = 1;
  let finish = () => {};
  const done = new Promise<void>((resolve) => {
    finish = resolve;
  });
  u.onboundary = (e) => {
    if (e.name === "word") onWord();
  };
  u.onend = () => finish();
  u.onerror = () => finish();
  synth.speak(u);
  // Some voices never fire onend; fall back to a length-based timeout.
  const guard = window.setTimeout(finish, 2500 + text.length * 90);
  done.then(() => window.clearTimeout(guard));
  return {
    done,
    cancel: () => {
      synth.cancel();
      finish();
    },
  };
}

/** Mic input level (0–1, smoothed) for the blob. */
export class MicLevel {
  level = 0;
  private stream: MediaStream | null = null;
  private ctx: AudioContext | null = null;
  private raf = 0;

  async start(): Promise<void> {
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    this.ctx = new AudioContext();
    const src = this.ctx.createMediaStreamSource(this.stream);
    const an = this.ctx.createAnalyser();
    an.fftSize = 512;
    src.connect(an);
    const buf = new Uint8Array(an.fftSize);
    const tick = () => {
      an.getByteTimeDomainData(buf);
      let sum = 0;
      for (let i = 0; i < buf.length; i++) {
        const v = (buf[i] - 128) / 128;
        sum += v * v;
      }
      const rms = Math.sqrt(sum / buf.length);
      const target = Math.min(1, rms * 6);
      this.level += (target - this.level) * (target > this.level ? 0.35 : 0.08);
      this.raf = requestAnimationFrame(tick);
    };
    tick();
  }

  stop(): void {
    cancelAnimationFrame(this.raf);
    this.stream?.getTracks().forEach((t) => t.stop());
    this.ctx?.close();
    this.stream = null;
    this.ctx = null;
    this.level = 0;
  }
}

/**
 * Plays the interviewer's MP3s (GET /api/interviews/{id}/audio/{hash}) through an
 * AnalyserNode so `level` follows the voice. Create it in a click handler so the
 * AudioContext may start (autoplay policy).
 */
export class TtsPlayer {
  level = 0;
  private ctx: AudioContext;
  private source: AudioBufferSourceNode | null = null;
  private raf = 0;
  private finish: (() => void) | null = null;

  constructor() {
    this.ctx = new AudioContext();
  }

  /** Fetch and decode; start these early so playback doesn't wait on the network. */
  async load(url: string): Promise<AudioBuffer> {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`speech ${res.status}`);
    return this.ctx.decodeAudioData(await res.arrayBuffer());
  }

  /** Resolves when the clip ends or stop() is called. */
  async play(buffer: AudioBuffer, onPulse: () => void): Promise<void> {
    this.stop();
    if (this.ctx.state === "suspended") await this.ctx.resume();
    const src = this.ctx.createBufferSource();
    src.buffer = buffer;
    const an = this.ctx.createAnalyser();
    an.fftSize = 512;
    src.connect(an);
    an.connect(this.ctx.destination);
    this.source = src;
    const buf = new Uint8Array(an.fftSize);
    let loud = false;
    const tick = () => {
      an.getByteTimeDomainData(buf);
      let sum = 0;
      for (let i = 0; i < buf.length; i++) {
        const v = (buf[i] - 128) / 128;
        sum += v * v;
      }
      const target = Math.min(1, Math.sqrt(sum / buf.length) * 5);
      this.level += (target - this.level) * (target > this.level ? 0.4 : 0.1);
      // A ripple per syllable-ish burst, like the word boundaries of the browser voice.
      if (target > 0.35 && !loud) onPulse();
      loud = target > 0.25;
      this.raf = requestAnimationFrame(tick);
    };
    const done = new Promise<void>((resolve) => {
      this.finish = resolve;
      src.onended = () => resolve();
    });
    src.start();
    tick();
    await done;
    cancelAnimationFrame(this.raf);
    this.level = 0;
    this.source = null;
    this.finish = null;
  }

  stop(): void {
    try {
      this.source?.stop();
    } catch {
      // already stopped
    }
    this.finish?.();
  }

  close(): void {
    this.stop();
    void this.ctx.close();
  }
}
