"use client";

// The AI voice interview after a submitted session (F5). Ported from the showcase's
// interview room (showcase/components/interview/Interview.tsx: consent, orb, live
// transcript, timer, typed fallback), with its scripted plan replaced by the backend:
// POST /interviews/{id}/start and /turn decide what is said, and the interviewer's voice
// is Featherless TTS through the backend (browser voice as fallback). Never scored.
import { useEffect, useRef, useState } from "react";
import { api, ApiError, API_BASE, type InterviewBlock, type InterviewSay, type InterviewState } from "@/lib/api";
import OracleOrb, { type OrbSignal, type OrbState } from "./OracleOrb";
import { createRecognition, MicLevel, recognitionSupported, speak, TtsPlayer, ttsSupported, type Recognition } from "./speech";

type Turn = { id: number; role: "interviewer" | "candidate"; text: string };
type Phase = "loading" | "missing" | "consent" | "live" | "done";

const CAPTION: Record<OrbState, string> = { idle: "Ready", listening: "Listening", thinking: "Thinking", speaking: "Speaking" };
const BLOCK_LABEL: Record<InterviewBlock, string> = { role: "Role", portfolio: "Portfolio", submission: "Your code" };

function clock(s: number): string {
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

export default function Interview({ sessionId }: { sessionId: string }) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [info, setInfo] = useState<{ company: string; role: string } | null>(null);
  const [ivState, setIvState] = useState<InterviewState | null>(null);
  const [inputMode, setInputMode] = useState<"voice" | "text">("voice");
  const [voiceOut, setVoiceOut] = useState(true);
  const [consent, setConsent] = useState(false);
  const [canListen, setCanListen] = useState(true);

  const [agent, setAgentState] = useState<OrbState>("idle");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [interim, setInterim] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [micOn, setMicOn] = useState(true);
  const [typed, setTyped] = useState("");

  const signal = useRef<OrbSignal>({ level: 0, pulses: 0 }).current;
  const r = useRef({
    live: false,
    agent: "idle" as OrbState,
    nextId: 1,
    voiceIn: false,
    voiceOut: true,
    micOn: true,
    rec: null as Recognition | null,
    recWanted: false,
    recActive: false,
    mic: null as MicLevel | null,
    tts: null as TtsPlayer | null,
    speech: null as { cancel: () => void } | null,
    committed: "",
    current: "",
    silence: 0,
    startedMs: 0,
    maxSeconds: 720,
  }).current;

  useEffect(() => {
    api
      .getInterview(sessionId)
      .then((v) => {
        setCanListen(recognitionSupported());
        if (!recognitionSupported()) setInputMode("text");
        setInfo({ company: v.company, role: v.role });
        setIvState(v.state);
        setTurns(v.transcript.map((t, i) => ({ id: i + 1, role: t.speaker, text: t.text })));
        r.nextId = v.transcript.length + 1;
        setPhase(v.state.status === "done" ? "done" : "consent");
      })
      .catch((e) => {
        setPhase("missing");
        setNotice(e instanceof ApiError && e.status === 404 ? null : "Could not load the interview.");
      });
  }, [sessionId, r]);

  const setAgent = (s: OrbState) => {
    r.agent = s;
    setAgentState(s);
  };

  const addTurn = (role: Turn["role"], text: string) => {
    const turn = { id: r.nextId++, role, text };
    setTurns((t) => [...t, turn]);
  };

  // ---- listening (same loop as the showcase) ----

  const startRec = () => {
    r.recWanted = true;
    if (!r.rec || !r.voiceIn || !r.micOn || r.recActive) return;
    try {
      r.rec.start();
      r.recActive = true;
    } catch {
      // still closing; onend restarts it
    }
  };

  const stopRec = () => {
    r.recWanted = false;
    window.clearTimeout(r.silence);
    if (r.rec && r.recActive) r.rec.abort();
  };

  const heard = () => `${r.committed} ${r.current}`.trim();

  const attachRecognition = (rec: Recognition) => {
    rec.onresult = (e) => {
      if (!r.recWanted) return;
      let fin = "";
      let tmp = "";
      for (let i = 0; i < e.results.length; i++) {
        const res = e.results[i];
        if (res.isFinal) fin += res[0].transcript + " ";
        else tmp += res[0].transcript + " ";
      }
      r.current = fin.trim();
      setInterim(`${heard()} ${tmp}`.trim());
      // End of turn: a pause after speech. Longer while words are still unconfirmed.
      window.clearTimeout(r.silence);
      r.silence = window.setTimeout(
        () => {
          const text = `${heard()} ${tmp}`.trim();
          if (text && r.agent === "listening") void endAnswer(text);
        },
        tmp.trim() ? 3200 : 2000,
      );
    };
    rec.onerror = (e) => {
      if (e.error === "not-allowed" || e.error === "service-not-allowed") {
        r.voiceIn = false;
        setNotice("The browser blocked the microphone. Allow it from the address bar, or keep going by typing.");
      } else if (e.error === "network") {
        setNotice("Speech recognition needs a network connection in this browser. You can type your answers instead.");
      }
    };
    rec.onend = () => {
      r.recActive = false;
      r.committed = heard();
      r.current = "";
      if (r.recWanted && r.live && r.agent === "listening") startRec();
    };
  };

  const listen = () => {
    if (!r.live) return;
    r.committed = "";
    r.current = "";
    setInterim("");
    setAgent("listening");
    startRec();
  };

  // ---- speaking: Featherless voice via the backend, browser voice as fallback ----

  const pulse = () => {
    signal.pulses += 1;
  };

  const speakSegment = async (text: string, clip: Promise<AudioBuffer> | null) => {
    if (clip && r.tts) {
      try {
        await r.tts.play(await clip, pulse);
        return;
      } catch {
        setNotice("The interviewer's voice is unavailable; using the browser's voice.");
      }
    }
    if (r.voiceOut && ttsSupported()) {
      const h = speak(text, () => {
        pulse();
        signal.level = 0.85;
      });
      r.speech = h;
      await h.done;
      r.speech = null;
    } else {
      pulse();
      await new Promise((res) => setTimeout(res, 500 + text.length * 12));
    }
  };

  const say = async (out: InterviewSay) => {
    setIvState(out.state);
    // Start every download now so the next segment is ready when the first one ends.
    const clips = out.segments.map((s) => (r.voiceOut && r.tts ? r.tts.load(`${API_BASE}${s.audio_url}`) : null));
    clips.forEach((c) => c?.catch(() => undefined));
    addTurn("interviewer", out.say_text);
    setAgent("speaking");
    for (let i = 0; i < out.segments.length; i++) {
      if (!r.live) return;
      await speakSegment(out.segments[i].text, clips[i]);
    }
  };

  // ---- turn logic ----

  const stopAll = () => {
    r.live = false;
    r.tts?.stop();
    r.speech?.cancel();
    stopRec();
    r.rec?.abort();
    r.mic?.stop();
    r.mic = null;
  };

  const after = async (out: InterviewSay) => {
    await say(out);
    if (out.state.status === "done") {
      stopAll();
      setAgent("idle");
      setInterim("");
      setPhase("done");
    } else {
      listen();
    }
  };

  async function endAnswer(text: string) {
    if (!r.live || r.agent !== "listening" || !text.trim()) return;
    stopRec();
    setInterim("");
    addTurn("candidate", text);
    setAgent("thinking");
    try {
      await after(await api.interviewTurn(sessionId, text));
    } catch (e) {
      setNotice(e instanceof ApiError ? String(e.message) : "The interviewer could not reply. Try again.");
      listen();
    }
  }

  const finish = async () => {
    if (!r.live) return;
    stopRec();
    r.tts?.stop();
    r.speech?.cancel();
    setAgent("thinking");
    try {
      await after(await api.endInterview(sessionId));
    } catch {
      stopAll();
      setPhase("done");
    }
  };

  // ---- lifecycle ----

  const start = async () => {
    setNotice(null);
    r.voiceOut = voiceOut;
    r.voiceIn = inputMode === "voice" && canListen;
    r.micOn = true;
    setMicOn(true);
    // Created inside the click so the AudioContext is allowed to play.
    if (r.voiceOut) r.tts = new TtsPlayer();

    if (r.voiceIn) {
      try {
        const mic = new MicLevel();
        await mic.start();
        r.mic = mic;
        r.rec = createRecognition();
        if (r.rec) attachRecognition(r.rec);
      } catch {
        r.voiceIn = false;
        setNotice("No microphone available (blocked, missing or busy). You can still answer by typing.");
      }
    }

    r.live = true;
    setPhase("live");
    window.scrollTo(0, 0);
    try {
      const out = ivState?.status === "live" ? null : await api.startInterview(sessionId);
      if (out) {
        r.startedMs = out.state.started_ms ?? Date.now();
        r.maxSeconds = out.state.max_seconds;
        await after(out);
      } else {
        // Resuming after a reload: the last question is in the transcript above.
        r.startedMs = ivState?.started_ms ?? Date.now();
        r.maxSeconds = ivState?.max_seconds ?? r.maxSeconds;
        listen();
      }
    } catch (e) {
      stopAll();
      setPhase("consent");
      setNotice(e instanceof ApiError ? String(e.message) : "Could not start the interview.");
    }
  };

  // Clock; the server ends the interview at the time limit on the next answer.
  useEffect(() => {
    if (phase !== "live") return;
    const id = window.setInterval(() => {
      if (r.startedMs) setElapsed(Math.min(r.maxSeconds, Math.floor((Date.now() - r.startedMs) / 1000)));
    }, 500);
    return () => window.clearInterval(id);
  }, [phase, r]);

  // Feed the orb: mic level while listening, the TTS playback level while speaking.
  useEffect(() => {
    if (phase !== "live") return;
    let raf = 0;
    const tick = () => {
      if (r.agent === "listening" && r.mic && r.micOn) signal.level = r.mic.level;
      else if (r.agent === "speaking" && r.tts && r.tts.level > 0) signal.level = r.tts.level;
      else signal.level *= 0.93;
      raf = requestAnimationFrame(tick);
    };
    tick();
    return () => cancelAnimationFrame(raf);
  }, [phase, r, signal]);

  useEffect(
    () => () => {
      stopAll();
      r.tts?.close();
    },
    [], // eslint-disable-line react-hooks/exhaustive-deps
  );

  const log = useRef<HTMLOListElement>(null);
  useEffect(() => {
    log.current?.scrollTo({ top: log.current.scrollHeight, behavior: "smooth" });
  }, [turns, interim]);

  const toggleMic = () => {
    r.micOn = !r.micOn;
    setMicOn(r.micOn);
    if (r.micOn && r.agent === "listening") startRec();
    if (!r.micOn) stopRec();
  };

  const submitTyped = (e: React.FormEvent) => {
    e.preventDefault();
    const text = typed.trim();
    if (!text || r.agent !== "listening") return;
    setTyped("");
    void endAnswer(text);
  };

  const ready = inputMode === "text" || consent;
  const blocks = ivState?.blocks ?? [];
  const cursor = ivState?.question_index ?? 0;

  // ---------------- render ----------------

  return (
    <div className="iv" data-testid="interview">
      <header className="iv-top">
        <div className="wrap iv-top-in">
          <span className="hdr-mark">Assay</span>
          <span className="iv-crumb">
            AI interview{info ? `: ${info.role} at ${info.company}` : ""}
          </span>
          {phase === "live" && (
            <span className="iv-timer" role="timer" aria-label="Elapsed time">
              <i aria-hidden />
              {clock(elapsed)} <span className="muted">/ {clock(r.maxSeconds)}</span>
            </span>
          )}
        </div>
      </header>

      {phase === "loading" && <main className="wrap iv-setup"><p className="small">Loading…</p></main>}

      {phase === "missing" && (
        <main className="wrap iv-setup">
          <div className="iv-setup-intro">
            <p className="label">AI interview</p>
            <h1 className="h2">No interview here yet.</h1>
            <p>{notice ?? "The recruiter hasn't set up an interview for this session."}</p>
          </div>
        </main>
      )}

      {phase === "consent" && info && (
        <main className="wrap iv-setup">
          <div className="iv-setup-intro">
            <p className="label">AI interview</p>
            <h1 className="h2">Talk through your own work, out loud.</h1>
            <p>
              A short voice interview for the {info.role} role at {info.company}, with an AI interviewer: questions
              about the role, one of your projects and the code you just submitted, at most one follow-up each. It
              never changes your assessment score.
            </p>
            <div className="iv-preview">
              <OracleOrb state="idle" signal={signal} className="iv-blob" />
            </div>
          </div>

          <form
            className="iv-form"
            onSubmit={(e) => {
              e.preventDefault();
              if (ready) void start();
            }}
          >
            <fieldset className="iv-field">
              <legend>Answer by</legend>
              <div className="iv-seg iv-seg-2" role="radiogroup">
                <label className="iv-opt" data-on={inputMode === "voice"} data-off={!canListen}>
                  <input
                    type="radio"
                    name="mode"
                    checked={inputMode === "voice"}
                    disabled={!canListen}
                    onChange={() => setInputMode("voice")}
                  />
                  <span className="iv-opt-name">Speaking</span>
                  <span className="small">{canListen ? "Microphone, with typing as a fallback" : "Needs Chrome or Edge"}</span>
                </label>
                <label className="iv-opt" data-on={inputMode === "text"}>
                  <input type="radio" name="mode" checked={inputMode === "text"} onChange={() => setInputMode("text")} />
                  <span className="iv-opt-name">Typing</span>
                  <span className="small">No microphone needed</span>
                </label>
              </div>
            </fieldset>

            <label className="iv-check">
              <input type="checkbox" checked={voiceOut} onChange={(e) => setVoiceOut(e.target.checked)} />
              <span>Interviewer speaks aloud (generated voice)</span>
            </label>

            {inputMode === "voice" && (
              <label className="iv-check iv-consent">
                <input
                  type="checkbox"
                  checked={consent}
                  onChange={(e) => setConsent(e.target.checked)}
                  data-testid="consent"
                />
                <span>
                  I agree to use my microphone. Speech recognition is done by the browser, and Chrome or Edge may send
                  the audio to Google or Microsoft to turn it into text. We store only the text transcript, which the
                  recruiter sees with your report; no audio is recorded or stored.
                </span>
              </label>
            )}

            {notice && (
              <p className="iv-notice" role="alert">
                {notice}
              </p>
            )}
            <button type="submit" className="iv-start" disabled={!ready} data-testid="start-interview">
              {ivState?.status === "live" ? "Resume the interview" : "Start the interview"}
            </button>
          </form>
        </main>
      )}

      {(phase === "live" || phase === "done") && (
        <main className="wrap iv-room">
          <ol className="iv-ticks" aria-label="Interview progress">
            {blocks.map((b, i) => (
              <li
                key={i}
                data-s={i < cursor || phase === "done" ? "done" : i === cursor ? "now" : "next"}
                title={BLOCK_LABEL[b]}
              >
                <span>{BLOCK_LABEL[b]}</span>
              </li>
            ))}
          </ol>

          <div className="iv-stage">
            <figure className="iv-orb">
              <OracleOrb state={agent} signal={signal} className="iv-blob" />
              <figcaption>
                <span className="orb-state" aria-live="polite">
                  {phase === "done" ? "Finished" : CAPTION[agent]}
                </span>
                {phase === "live" && agent === "listening" && r.voiceIn && (
                  <span className="small">{micOn ? "Pause for two seconds when you're done." : "Mic paused. Type below."}</span>
                )}
              </figcaption>
            </figure>

            <section className="iv-log" aria-label="Transcript">
              <ol ref={log} aria-live="polite" tabIndex={0} data-testid="transcript">
                {turns.map((t) => (
                  <li key={t.id} data-r={t.role}>
                    <span className="iv-who">{t.role === "interviewer" ? "Interviewer (AI)" : "You"}</span>
                    <p>{t.text}</p>
                  </li>
                ))}
                {interim && (
                  <li data-r="candidate" data-interim>
                    <span className="iv-who">You</span>
                    <p>{interim}</p>
                  </li>
                )}
              </ol>
            </section>
          </div>

          {notice && (
            <p className="iv-notice" role="alert">
              {notice}
            </p>
          )}

          {phase === "live" && (
            <div className="iv-controls">
              <div className="iv-buttons">
                {r.voiceIn && (
                  <button type="button" onClick={toggleMic} aria-pressed={!micOn}>
                    {micOn ? "Pause mic" : "Resume mic"}
                  </button>
                )}
                {r.voiceIn && (
                  <button
                    type="button"
                    onClick={() => void endAnswer(interim)}
                    disabled={agent !== "listening" || !interim}
                  >
                    Done answering
                  </button>
                )}
                <button type="button" className="iv-end" onClick={() => void finish()}>
                  End interview
                </button>
              </div>
              <form className="iv-type" onSubmit={submitTyped}>
                <label htmlFor="iv-typed" className="sr-only">
                  Type your answer
                </label>
                <input
                  id="iv-typed"
                  value={typed}
                  onChange={(e) => setTyped(e.target.value)}
                  placeholder="Or type your answer and press Enter"
                  autoComplete="off"
                  data-testid="typed-answer"
                />
                <button type="submit" disabled={!typed.trim() || agent !== "listening"}>
                  Send
                </button>
              </form>
            </div>
          )}

          {phase === "done" && (
            <section className="iv-notes">
              <h2 className="h3">Thank you</h2>
              <p className="small">
                The transcript goes to the recruiter with your report. The interview is not part of your score.
              </p>
            </section>
          )}
        </main>
      )}
    </div>
  );
}
