"use client";
// The Oracle: a ten-minute voice interview (docs/INTERVIEWER.md). Listening uses the
// browser's Web Speech API; the demo voice is the browser's speechSynthesis (a live
// session plays Featherless TTS through the backend proxy). Transcripts are kept, audio
// is not. The interview is shown in the report and never affects the score.
import { useEffect, useRef, useState } from "react";
import { JourneyBar, useCountdown } from "@/components/olympus/Chrome";
import Engraving from "@/components/olympus/Engraving";
import { IconCheck, IconMic, IconMicOff, IconSkip, IconStop } from "@/components/olympus/Icons";
import { Btn } from "@/components/olympus/Kit";
import Meander from "@/components/olympus/Meander";
import OracleOrb, { type OrbState } from "@/components/olympus/OracleOrb";
import { useNav } from "@/components/olympus/Shell";
import { firstName, oracleQuestions, ORACLE_SECONDS } from "@/lib/olympus/demo";
import { updateJourney, useJourney } from "@/lib/olympus/journey";
import { gsap, useGsap } from "@/lib/olympus/motion";

type Recognition = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((e: { resultIndex: number; results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }> }) => void) | null;
  onend: (() => void) | null;
  onerror: ((e: { error: string }) => void) | null;
};
type RecognitionCtor = new () => Recognition;

const STATE_LABEL: Record<OrbState, string> = {
  idle: "The Oracle is waiting",
  speaking: "The Oracle speaks",
  listening: "The Oracle listens",
  thinking: "The Oracle contemplates",
};

function pickVoice(): SpeechSynthesisVoice | null {
  const voices = window.speechSynthesis?.getVoices() ?? [];
  const prefer = ["Google UK English Female", "Microsoft Aria", "Microsoft Jenny", "Samantha", "Google US English"];
  for (const name of prefer) {
    const v = voices.find((x) => x.name.includes(name));
    if (v) return v;
  }
  return voices.find((v) => v.lang.startsWith("en")) ?? null;
}

export default function Oracle() {
  const journey = useJourney();
  const { navigate } = useNav();
  const [phase, setPhase] = useState<"consent" | "live" | "done">("consent");
  const [orb, setOrb] = useState<OrbState>("idle");
  const [questions, setQuestions] = useState(() => oracleQuestions(journey));
  const [qi, setQi] = useState(0);
  const [shownWords, setShownWords] = useState(0);
  const [finalText, setFinalText] = useState("");
  const [interim, setInterim] = useState("");
  const [typed, setTyped] = useState("");
  const [mode, setMode] = useState<"voice" | "text">("voice");
  const [muted, setMuted] = useState(false);
  const [consent, setConsent] = useState(false);
  const [answers, setAnswers] = useState<{ q: string; a: string }[]>([]);

  const level = useRef(0);
  const orbRef = useRef<OrbState>("idle");
  const mutedRef = useRef(false);
  const audio = useRef<{ ctx: AudioContext; analyser: AnalyserNode; stream: MediaStream; data: Uint8Array<ArrayBuffer> } | null>(null);
  const recog = useRef<Recognition | null>(null);
  const listening = useRef(false);
  const finalRef = useRef("");
  const interimRef = useRef("");
  const timers = useRef<number[]>([]);
  const startedAt = useRef(0);
  const qiRef = useRef(0);
  const answersRef = useRef<{ q: string; a: string }[]>([]);

  const finishRef = useRef<() => void>(() => {});
  const seconds = useCountdown(ORACLE_SECONDS, phase === "live", () => finishRef.current());

  useEffect(() => {
    orbRef.current = orb;
  }, [orb]);
  useEffect(() => {
    mutedRef.current = muted;
  }, [muted]);

  // Drives the orb's level: mic RMS while listening, a speech-like envelope while speaking.
  useEffect(() => {
    if (phase !== "live") return;
    let raf = 0;
    const loop = (now: number) => {
      const t = now / 1000;
      const s = orbRef.current;
      if (s === "listening" && audio.current && !mutedRef.current) {
        const { analyser, data } = audio.current;
        analyser.getByteTimeDomainData(data);
        let sum = 0;
        for (let i = 0; i < data.length; i++) sum += ((data[i] - 128) / 128) ** 2;
        level.current = Math.min(1, Math.sqrt(sum / data.length) * 5.5);
      } else if (s === "speaking") {
        level.current = 0.22 + 0.38 * Math.abs(Math.sin(t * 7.3) * Math.sin(t * 2.9 + Math.sin(t * 1.3)));
      } else if (s === "thinking") {
        level.current = 0.1 + 0.05 * Math.sin(t * 2);
      } else {
        level.current = 0.03;
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [phase]);

  useEffect(
    () => () => {
      timers.current.forEach((id) => window.clearTimeout(id));
      window.speechSynthesis?.cancel();
      recog.current?.abort();
      audio.current?.stream.getTracks().forEach((tr) => tr.stop());
      audio.current?.ctx.close();
    },
    [],
  );

  const later = (fn: () => void, ms: number) => timers.current.push(window.setTimeout(fn, ms));

  const speak = (text: string, done: () => void) => {
    const words = text.split(/\s+/).length;
    setShownWords(0);
    let shown = 0;
    const reveal = window.setInterval(() => {
      shown += 1;
      setShownWords(shown);
      if (shown >= words) window.clearInterval(reveal);
    }, 290);
    let ended = false;
    const end = () => {
      if (ended) return;
      ended = true;
      window.clearInterval(reveal);
      setShownWords(words);
      done();
    };
    const synth = window.speechSynthesis;
    if (synth) {
      const u = new SpeechSynthesisUtterance(text);
      u.voice = pickVoice();
      u.rate = 0.97;
      u.pitch = 0.92;
      u.onend = end;
      u.onerror = end;
      synth.cancel();
      synth.speak(u);
      later(end, words * 480 + 2500); // safety net when no voice is installed
    } else {
      later(end, words * 300 + 600);
    }
  };

  const startListening = () => {
    finalRef.current = "";
    interimRef.current = "";
    setFinalText("");
    setInterim("");
    setTyped("");
    listening.current = true;
    const Ctor = (window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor }).SpeechRecognition ??
      (window as unknown as { webkitSpeechRecognition?: RecognitionCtor }).webkitSpeechRecognition;
    if (mode !== "voice" || !Ctor || mutedRef.current) return;
    const r = new Ctor();
    r.continuous = true;
    r.interimResults = true;
    r.lang = "en-US";
    r.onresult = (e) => {
      let live = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const res = e.results[i];
        if (res.isFinal) finalRef.current += `${res[0].transcript.trim()} `;
        else live += res[0].transcript;
      }
      interimRef.current = live;
      setFinalText(finalRef.current);
      setInterim(live);
    };
    r.onerror = (e) => {
      if (e.error === "not-allowed" || e.error === "service-not-allowed") setMode("text");
    };
    r.onend = () => {
      if (listening.current && !mutedRef.current) {
        try {
          r.start();
        } catch {}
      }
    };
    try {
      r.start();
      recog.current = r;
    } catch {
      setMode("text");
    }
  };

  const stopListening = () => {
    listening.current = false;
    recog.current?.stop();
    recog.current = null;
  };

  const ask = (i: number) => {
    qiRef.current = i;
    setQi(i);
    setOrb("speaking");
    speak(questions[i].text, () => {
      setOrb("listening");
      startListening();
    });
  };

  const enter = async () => {
    let voice = true;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
      const ctx = new AudioContext();
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 1024;
      ctx.createMediaStreamSource(stream).connect(analyser);
      audio.current = { ctx, analyser, stream, data: new Uint8Array(new ArrayBuffer(analyser.fftSize)) };
    } catch {
      voice = false;
    }
    setMode(voice ? "voice" : "text");
    setQuestions(oracleQuestions(journey));
    startedAt.current = Date.now();
    setPhase("live");
    later(() => ask(0), 1400);
  };

  const record = (): { q: string; a: string }[] => {
    const a = (typed || `${finalRef.current}${interimRef.current}`).trim();
    const next = [...answersRef.current, { q: questions[qiRef.current].text, a: a || "(no answer)" }];
    answersRef.current = next;
    setAnswers(next);
    return next;
  };

  const doneAnswering = () => {
    if (orbRef.current !== "listening") return;
    stopListening();
    record();
    setOrb("thinking");
    const next = qiRef.current + 1;
    later(() => (next < questions.length ? ask(next) : finish()), 1500);
  };

  const finish = () => {
    if (phase === "done") return;
    timers.current.forEach((id) => window.clearTimeout(id));
    window.speechSynthesis?.cancel();
    const all = orbRef.current === "listening" ? (stopListening(), record()) : answersRef.current;
    setOrb("idle");
    setPhase("done");
    updateJourney({
      oracle: {
        answered: all.filter((x) => x.a !== "(no answer)").length,
        total: questions.length,
        seconds: Math.round((Date.now() - startedAt.current) / 1000),
        transcript: all,
        completedAt: new Date().toISOString(),
      },
    });
    audio.current?.stream.getTracks().forEach((tr) => tr.stop());
  };

  useEffect(() => {
    finishRef.current = finish;
  });

  const toggleMute = () => {
    const m = !muted;
    setMuted(m);
    mutedRef.current = m;
    if (orbRef.current !== "listening") return;
    if (m) stopListening();
    else startListening();
  };

  const q = questions[qi];
  const words = q.text.split(/\s+/);

  return (
    <div className="relative flex min-h-[100dvh] flex-col overflow-hidden">
      <Backdrop active={phase === "live"} />
      <JourneyBar night seconds={phase === "live" ? seconds : undefined} />

      {phase === "consent" && <Consent name={firstName(journey.candidate)} consent={consent} setConsent={setConsent} onEnter={enter} />}

      {phase === "live" && (
        <main className="relative z-10 flex flex-1 flex-col items-center justify-between px-[var(--gutter)] pb-8 pt-4">
          <p className="mono flex items-center gap-2.5 text-[12px] uppercase tracking-[0.18em] text-[rgba(233,228,212,0.7)]" aria-live="polite">
            <span className="pulse-dot" style={{ color: orb === "listening" ? "#7ff0d8" : orb === "thinking" ? "#b49bff" : "var(--gold-bright)" }} />
            {STATE_LABEL[orb]}
          </p>

          <div className="relative grid place-items-center">
            <OracleOrb state={orb} level={level} className="h-[min(52vh,92vw,560px)] w-[min(52vh,92vw,560px)]" />
          </div>

          <div className="w-full max-w-[880px] text-center">
            <p className="eyebrow mb-4">
              {q.block} · question {qi + 1} of {questions.length}
            </p>
            <h1 className="display min-h-[2.3em] text-[clamp(24px,3vw,40px)] italic leading-[1.15]" aria-live="polite">
              {words.map((w, i) => (
                <span key={i} className="inline-block transition-[opacity,filter,transform] duration-500" style={{ opacity: i < shownWords ? 1 : 0.08, filter: i < shownWords ? "none" : "blur(4px)", transform: i < shownWords ? "none" : "translateY(4px)" }}>
                  {w}&nbsp;
                </span>
              ))}
            </h1>

            <div className="mx-auto mt-5 min-h-[56px] max-w-[720px]">
              {mode === "voice" ? (
                <p className="text-[15.5px] leading-relaxed text-[rgba(233,228,212,0.85)]">
                  {finalText}
                  <span className="text-[rgba(233,228,212,0.45)]">{interim}</span>
                  {!finalText && !interim && orb === "listening" && <span className="text-[rgba(233,228,212,0.4)]">{muted ? "Microphone muted." : "Speak when you're ready — your words appear here."}</span>}
                </p>
              ) : (
                orb === "listening" && (
                  <textarea
                    autoFocus
                    value={typed}
                    onChange={(e) => setTyped(e.target.value)}
                    placeholder="Microphone unavailable — type your answer here."
                    rows={3}
                    className="w-full resize-none rounded-[16px] bg-[rgba(233,228,212,0.06)] p-4 text-[15px] text-[var(--moon)] outline-none shadow-[inset_0_0_0_1px_rgba(233,228,212,0.18)] placeholder:text-[rgba(233,228,212,0.35)] focus:shadow-[inset_0_0_0_1px_var(--gold-bright)]"
                  />
                )
              )}
            </div>

            <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
              <button
                onClick={toggleMute}
                disabled={mode !== "voice"}
                aria-pressed={muted}
                aria-label={muted ? "Unmute microphone" : "Mute microphone"}
                className="grid h-12 w-12 place-items-center rounded-full transition-colors disabled:opacity-30"
                style={{ background: muted ? "var(--fail)" : "rgba(233,228,212,0.08)", boxShadow: "inset 0 0 0 1px rgba(233,228,212,0.2)" }}
              >
                {muted ? <IconMicOff size={19} /> : <IconMic size={19} />}
              </button>
              <Btn variant="moon" size="sm" magnetic={false} onClick={doneAnswering} disabled={orb !== "listening"} icon={<IconSkip size={12} />}>
                {qi + 1 < questions.length ? "Done answering" : "Final answer"}
              </Btn>
              <button
                onClick={finish}
                className="inline-flex h-10 items-center gap-2 rounded-full px-4 text-[13.5px] text-[rgba(233,228,212,0.75)] shadow-[inset_0_0_0_1px_rgba(233,228,212,0.2)] transition-colors hover:bg-[rgba(181,71,58,0.25)]"
              >
                <IconStop size={14} /> End interview
              </button>
            </div>
          </div>

          <ol className="absolute right-[var(--gutter)] top-1/2 hidden -translate-y-1/2 flex-col gap-3 xl:flex" aria-label="Questions">
            {questions.map((x, i) => (
              <li key={i} className="flex items-center justify-end gap-3 text-[12px]" style={{ opacity: i === qi ? 1 : i < qi ? 0.6 : 0.3 }}>
                <span className="text-right">{x.block}</span>
                <span
                  className="numeral grid h-7 w-7 place-items-center rounded-full text-[13px]"
                  style={{ background: i < qi ? "var(--gold-bright)" : "transparent", color: i < qi ? "var(--night)" : "var(--moon)", boxShadow: i < qi ? "none" : `inset 0 0 0 1px rgba(233,228,212,${i === qi ? 0.8 : 0.3})` }}
                >
                  {i < qi ? <IconCheck size={12} strokeWidth={2.4} /> : ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii"][i]}
                </span>
              </li>
            ))}
          </ol>
        </main>
      )}

      {phase === "done" && <Done answers={answers} total={questions.length} onNext={() => navigate("/verdict")} />}
    </div>
  );
}

function Backdrop({ active }: { active: boolean }) {
  return (
    <div className="pointer-events-none absolute inset-0" aria-hidden="true">
      <div className="absolute left-1/2 top-[46%] w-[min(140vh,1200px)] -translate-x-1/2 -translate-y-1/2 transition-opacity duration-[2s]" style={{ opacity: active ? 0.07 : 0.11 }}>
        <div className="spin-slow">
          <Engraving name="starchart-1" className="w-full" style={{ color: "var(--moon)" }} />
        </div>
      </div>
      <svg className="absolute left-1/2 top-[46%] h-[min(110vh,940px)] w-[min(110vh,940px)] -translate-x-1/2 -translate-y-1/2" viewBox="0 0 400 400">
        <circle cx="200" cy="200" r="196" fill="none" stroke="rgba(233,228,212,0.08)" strokeDasharray="1 6" />
        <circle cx="200" cy="200" r="150" fill="none" stroke="rgba(226,194,134,0.12)" />
        <circle cx="200" cy="200" r="110" fill="none" stroke="rgba(233,228,212,0.05)" />
      </svg>
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_50%_45%,transparent_30%,var(--night)_78%)]" />
    </div>
  );
}

function Consent({ name, consent, setConsent, onEnter }: { name: string; consent: boolean; setConsent: (v: boolean) => void; onEnter: () => void }) {
  const root = useRef<HTMLDivElement>(null);
  useGsap(root, (reduced) => {
    if (reduced) return;
    gsap.from(".oc-in", { y: 40, opacity: 0, duration: 1.3, stagger: 0.08, ease: "expo.out", delay: 0.2 });
    gsap.from(".oc-sun", { scale: 0.6, opacity: 0, rotate: -30, duration: 2.2, ease: "expo.out" });
  });
  return (
    <main ref={root} className="relative z-10 mx-auto grid w-full max-w-[1300px] flex-1 items-center gap-12 px-[var(--gutter)] py-12 lg:grid-cols-[1fr_1fr]">
      <div className="relative hidden justify-center lg:flex">
        <div className="oc-sun w-[min(34vw,440px)]">
          <Engraving name="sun" fade className="w-full" style={{ color: "var(--gold-bright)" }} label="The sun of Delphi" />
        </div>
      </div>
      <div>
        <p className="eyebrow oc-in mb-6">Round Ⅳ · The Oracle of Delphi</p>
        <h1 className="display oc-in text-[clamp(48px,5.6vw,92px)]">
          Speak with the <em style={{ color: "var(--gold-bright)" }}>Oracle</em>, {name}.
        </h1>
        <p className="oc-in mt-6 max-w-[520px] text-[17px] leading-relaxed text-[rgba(233,228,212,0.72)]">
          Ten minutes, up to eight questions about your own work and the trials you just completed. Answer aloud; the Oracle listens,
          then moves on when you say you&apos;re done.
        </p>
        <ul className="oc-in mt-8 space-y-3 text-[14.5px] text-[rgba(233,228,212,0.82)]">
          {[
            "We need your microphone. Speech is transcribed by your browser's speech service, which may send audio to the browser vendor (e.g. Google for Chrome).",
            "We keep the transcript, never the audio.",
            "The interview appears in your report but never changes your score.",
            "No questions about age, family, religion, health or nationality — ever.",
          ].map((t) => (
            <li key={t} className="flex gap-3">
              <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rotate-45 bg-[var(--gold-bright)]" />
              {t}
            </li>
          ))}
        </ul>
        <label className="oc-in mt-8 flex cursor-pointer items-center gap-3 text-[15px]">
          <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="h-5 w-5 accent-[var(--gold-bright)]" />I understand and consent to the
          voice interview.
        </label>
        <div className="oc-in mt-8">
          <Btn variant="moon" onClick={onEnter} disabled={!consent}>
            Enter the adyton
          </Btn>
        </div>
      </div>
    </main>
  );
}

function Done({ answers, total, onNext }: { answers: { q: string; a: string }[]; total: number; onNext: () => void }) {
  const root = useRef<HTMLDivElement>(null);
  useGsap(root, (reduced) => {
    if (reduced) return;
    gsap.from(".od-in", { y: 40, opacity: 0, duration: 1.3, stagger: 0.08, ease: "expo.out" });
    gsap.from(".od-wreath", { scale: 0.5, rotate: -90, opacity: 0, duration: 1.8, ease: "expo.out" });
  });
  return (
    <main ref={root} className="relative z-10 mx-auto flex w-full max-w-[860px] flex-1 flex-col items-center px-[var(--gutter)] py-16 text-center">
      <Engraving name="wreath" className="od-wreath w-28" style={{ color: "var(--gold-bright)" }} />
      <p className="eyebrow od-in mt-8">The interview is sealed</p>
      <h1 className="display od-in mt-4 text-[clamp(48px,6vw,96px)]">
        The Oracle has <em style={{ color: "var(--gold-bright)" }}>spoken</em>.
      </h1>
      <p className="od-in mt-5 text-[17px] text-[rgba(233,228,212,0.72)]">
        {answers.filter((a) => a.a !== "(no answer)").length} of {total} questions answered. Your transcript joins the report — shown, never scored.
      </p>
      <div className="od-in mt-10 w-full space-y-3 text-left">
        {answers.slice(0, 3).map((x, i) => (
          <div key={i} className="rounded-[18px] bg-[rgba(233,228,212,0.05)] p-5 shadow-[inset_0_0_0_1px_rgba(233,228,212,0.1)]">
            <p className="font-[family-name:var(--display)] text-[18px] italic text-[rgba(233,228,212,0.9)]">{x.q}</p>
            <p className="mt-2 text-[14px] text-[rgba(233,228,212,0.6)]">{x.a}</p>
          </div>
        ))}
      </div>
      <Meander className="od-in my-10 text-[var(--moon)] opacity-20" height={12} />
      <div className="od-in">
        <Btn variant="moon" onClick={onNext}>
          Generate your verdict
        </Btn>
      </div>
    </main>
  );
}
