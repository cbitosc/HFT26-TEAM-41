"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import Chip from "@/components/Chip";
import { NAME, AGENT } from "@/lib/site";
import BlobStage, { type AgentState, type BlobSignal } from "./Blob";
import {
  ack,
  CLOSING,
  DEMO_SETUP,
  fill,
  fillerCount,
  greeting,
  MAX_SECONDS,
  MAX_TURNS,
  nextMove,
  planFor,
  SECTION_LABEL,
  TIME_UP,
  TRACK_LIST,
  words,
  type Question,
  type Setup,
} from "./plan";
import { createRecognition, MicLevel, recognitionSupported, speak, ttsSupported, type Recognition } from "./speech";

// Browser-only port of DeepInterview's live interview screen: same flow (setup,
// live room with stage + transcript + timer + typed fallback, then notes), with the
// LiveKit voice loop replaced by the Web Speech API and the LLM replaced by the
// scripted adaptive plan in plan.ts.

type Turn = {
  id: number;
  role: "interviewer" | "candidate";
  text: string;
  qid: string;
  kind?: "main" | "simpler" | "deeper";
  start?: number;
  end?: number;
};

type Phase = "setup" | "live" | "done";

const CAPTION: Record<AgentState, string> = {
  idle: "Ready",
  listening: "Listening",
  thinking: "Thinking",
  speaking: "Speaking",
};

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function clock(s: number): string {
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

const SKIP = /^\s*(next|skip|pass|next question)[.!]?\s*$/i;

export default function Interview() {
  const [phase, setPhase] = useState<Phase>("setup");
  const [setup, setSetup] = useState<Setup>({ name: "", project: "", stack: "", track: "backend" });
  const [inputMode, setInputMode] = useState<"voice" | "text">("voice");
  const [voiceOut, setVoiceOut] = useState(true);
  const [consent, setConsent] = useState(false);
  const [canListen, setCanListen] = useState(true);
  const [canSpeak, setCanSpeak] = useState(true);

  const [agent, setAgentState] = useState<AgentState>("idle");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [interim, setInterim] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [micOn, setMicOn] = useState(true);
  const [cursor, setCursor] = useState(0);
  const [typed, setTyped] = useState("");

  const signal = useRef<BlobSignal>({ level: 0, pulses: 0 }).current;
  const r = useRef({
    live: false,
    wrapping: false,
    agent: "idle" as AgentState,
    setup: DEMO_SETUP,
    plan: [] as Question[],
    cursor: 0,
    followupAsked: false,
    turnCount: 0,
    nextId: 1,
    voiceIn: false,
    voiceOut: true,
    micOn: true,
    rec: null as Recognition | null,
    recWanted: false,
    recActive: false,
    mic: null as MicLevel | null,
    speech: null as { cancel: () => void } | null,
    committed: "",
    current: "",
    answerStart: 0,
    silence: 0,
    startedAt: 0,
    turns: [] as Turn[],
  }).current;

  useEffect(() => {
    setCanListen(recognitionSupported());
    setCanSpeak(ttsSupported());
    if (!recognitionSupported()) setInputMode("text");
  }, []);

  const setAgent = (s: AgentState) => {
    r.agent = s;
    setAgentState(s);
  };

  const addTurn = (t: Omit<Turn, "id">) => {
    const turn = { ...t, id: r.nextId++ };
    r.turns = [...r.turns, turn];
    setTurns(r.turns);
  };

  // ---- listening ----

  // recWanted: we want to hear the candidate now. recActive: a recognition session
  // is open (cleared in onend). Chrome closes sessions on its own, so onend restarts.
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
      if (!r.answerStart) r.answerStart = Date.now();
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
      // Chrome ends recognition after a while; keep what it heard and restart.
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
    r.answerStart = 0;
    setInterim("");
    setAgent("listening");
    startRec();
  };

  // ---- speaking ----

  const say = async (text: string, qid: string, kind?: Turn["kind"]) => {
    if (!r.live) return;
    setAgent("speaking");
    addTurn({ role: "interviewer", text, qid, kind });
    if (r.voiceOut) {
      const h = speak(text, () => {
        signal.pulses += 1;
        signal.level = 0.85;
      });
      r.speech = h;
      await h.done;
      r.speech = null;
    } else {
      signal.pulses += 1;
      await sleep(500 + text.length * 12);
    }
  };

  const ask = async (q: Question, kind: "main" | "simpler" | "deeper", prefix = "") => {
    const text = kind === "main" ? q.text : kind === "simpler" ? q.simpler! : q.deeper!;
    await say(`${prefix}${prefix ? " " : ""}${fill(text, r.setup)}`, q.id, kind);
  };

  // ---- turn logic ----

  const stopAll = () => {
    r.live = false;
    r.speech?.cancel();
    stopRec();
    r.rec?.abort();
    r.mic?.stop();
    r.mic = null;
  };

  const finish = async (line: string | null) => {
    if (line) await say(line, "end");
    stopAll();
    setAgent("idle");
    setInterim("");
    setPhase("done");
  };

  const overLimit = () =>
    (Date.now() - r.startedAt) / 1000 >= MAX_SECONDS || r.turns.length >= MAX_TURNS;

  const advance = async () => {
    r.cursor += 1;
    r.followupAsked = false;
    setCursor(r.cursor);
    if (r.cursor >= r.plan.length) return finish(CLOSING);
    await ask(r.plan[r.cursor], "main", ack(r.turnCount));
    listen();
  };

  async function endAnswer(text: string, forceAdvance = false) {
    if (!r.live || r.agent !== "listening") return;
    stopRec();
    setInterim("");
    const q = r.plan[r.cursor];
    const skip = forceAdvance || SKIP.test(text);
    if (text && !SKIP.test(text)) {
      addTurn({
        role: "candidate",
        text,
        qid: q.id,
        start: r.answerStart || undefined,
        end: r.answerStart ? Date.now() : undefined,
      });
      r.turnCount += 1;
    }
    setAgent("thinking");
    await sleep(700);
    if (!r.live) return;
    if (overLimit()) return finish(TIME_UP);
    const move = skip ? "advance" : nextMove(q, words(text), r.followupAsked);
    if (move === "advance") return advance();
    r.followupAsked = true;
    await ask(q, move);
    listen();
  }

  // ---- lifecycle ----

  const start = async () => {
    setNotice(null);
    r.setup = setup;
    r.plan = planFor(setup);
    r.cursor = 0;
    r.followupAsked = false;
    r.turnCount = 0;
    r.turns = [];
    r.wrapping = false;
    r.voiceOut = voiceOut && canSpeak;
    r.voiceIn = inputMode === "voice" && canListen;
    r.micOn = true;
    setMicOn(true);
    setTurns([]);
    setCursor(0);
    setElapsed(0);

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
    r.startedAt = Date.now();
    setPhase("live");
    window.scrollTo(0, 0);
    await say(greeting(setup), "intro");
    await ask(r.plan[0], "main");
    listen();
  };

  // Clock and the hard time ceiling.
  useEffect(() => {
    if (phase !== "live") return;
    const id = window.setInterval(() => {
      const s = Math.floor((Date.now() - r.startedAt) / 1000);
      setElapsed(s);
      if (s >= MAX_SECONDS && !r.wrapping && r.agent === "listening") {
        r.wrapping = true;
        const text = `${heard()}`.trim();
        if (text) addTurn({ role: "candidate", text, qid: r.plan[r.cursor]?.id ?? "end" });
        stopRec();
        void finish(TIME_UP);
      }
    }, 500);
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase]);

  // Feed the blob: mic level while listening, a decaying word pulse while speaking.
  useEffect(() => {
    if (phase !== "live") return;
    let raf = 0;
    const tick = () => {
      if (r.agent === "listening" && r.mic && r.micOn) signal.level = r.mic.level;
      else signal.level *= 0.93;
      raf = requestAnimationFrame(tick);
    };
    tick();
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase]);

  useEffect(() => () => stopAll(), []); // eslint-disable-line react-hooks/exhaustive-deps

  // Keep the transcript scrolled to the newest line.
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

  const doneAnswering = () => {
    const text = interim.trim();
    if (text) void endAnswer(text);
  };

  const submitTyped = (e: React.FormEvent) => {
    e.preventDefault();
    const text = typed.trim();
    if (!text || r.agent !== "listening") return;
    setTyped("");
    void endAnswer(text);
  };

  const ready = setup.project.trim().length > 0 && (inputMode === "text" || consent);

  // ---------------- render ----------------

  return (
    <div className="iv dark">
      <header className="iv-top">
        <div className="wrap iv-top-in">
          <Link href="/" className="hdr-mark">
            {NAME}
          </Link>
          <span className="iv-crumb">AI interview, practice</span>
          {phase === "live" ? (
            <span className="iv-timer" role="timer" aria-label="Elapsed time">
              <i aria-hidden />
              {clock(elapsed)} <span className="muted">/ {clock(MAX_SECONDS)}</span>
            </span>
          ) : (
            <Link href="/" className="iv-back">
              Back to the site
            </Link>
          )}
        </div>
      </header>

      {phase === "setup" && (
        <main className="wrap iv-setup">
          <div className="iv-setup-intro">
            <p className="label">AI interview</p>
            <h1 className="h2">Talk through your own work, out loud.</h1>
            <p>
              A ten-minute practice interview about a project you built. The interviewer asks, listens, and follows up:
              an easier question when an answer is short, a harder one when it&apos;s detailed. It never touches a
              score.
            </p>
            <Chip s="progress">Browser demo: scripted adaptive plan, no model calls</Chip>
            <p className="small iv-credit">
              Flow and follow-up rules ported from{" "}
              <a href="https://github.com/ngoanpv/DeepInterview" target="_blank" rel="noreferrer">
                DeepInterview
              </a>{" "}
              (Apache-2.0). The full interviewer with Featherless is P4.7–P4.11.
            </p>
            <div className="iv-preview">
              <BlobStage state="idle" signal={signal} />
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
              <legend>Interview track</legend>
              <div className="iv-seg" role="radiogroup">
                {TRACK_LIST.map((t) => (
                  <label key={t.id} className="iv-opt" data-on={setup.track === t.id}>
                    <input
                      type="radio"
                      name="track"
                      value={t.id}
                      checked={setup.track === t.id}
                      onChange={() => setSetup({ ...setup, track: t.id })}
                    />
                    <span className="iv-opt-name">{t.label}</span>
                    <span className="small">{t.note}</span>
                  </label>
                ))}
              </div>
            </fieldset>

            <div className="iv-row">
              <label className="iv-field">
                <span className="iv-lab">Project</span>
                <input
                  value={setup.project}
                  onChange={(e) => setSetup({ ...setup, project: e.target.value })}
                  placeholder="the expenses API"
                  maxLength={60}
                  required
                />
              </label>
              <label className="iv-field">
                <span className="iv-lab">Its stack</span>
                <input
                  value={setup.stack}
                  onChange={(e) => setSetup({ ...setup, stack: e.target.value })}
                  placeholder="FastAPI and Postgres"
                  maxLength={60}
                />
              </label>
            </div>
            <label className="iv-field">
              <span className="iv-lab">What should {AGENT} call you? (optional)</span>
              <input
                value={setup.name}
                onChange={(e) => setSetup({ ...setup, name: e.target.value })}
                maxLength={30}
                autoComplete="given-name"
              />
            </label>

            <button type="button" className="iv-link" onClick={() => setSetup({ ...DEMO_SETUP, name: setup.name })}>
              Fill with the demo project
            </button>

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
                  <span className="small">{canListen ? "Microphone, with typing as a fallback" : "Needs Chrome, Edge or Safari"}</span>
                </label>
                <label className="iv-opt" data-on={inputMode === "text"}>
                  <input type="radio" name="mode" checked={inputMode === "text"} onChange={() => setInputMode("text")} />
                  <span className="iv-opt-name">Typing</span>
                  <span className="small">No microphone needed</span>
                </label>
              </div>
            </fieldset>

            <label className="iv-check">
              <input
                type="checkbox"
                checked={voiceOut && canSpeak}
                disabled={!canSpeak}
                onChange={(e) => setVoiceOut(e.target.checked)}
              />
              <span>Interviewer speaks aloud (the browser&apos;s built-in voice)</span>
            </label>

            {inputMode === "voice" && (
              <label className="iv-check iv-consent">
                <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
                <span>
                  I agree to use my microphone. Speech recognition is done by the browser, and Chrome, Edge or Safari
                  may send the audio to Google, Microsoft or Apple to turn it into text. This page keeps only the text
                  transcript, in this tab. Nothing is uploaded or saved by us, and no audio is recorded.
                </span>
              </label>
            )}

            <button type="submit" className="iv-start" disabled={!ready}>
              Start the interview
            </button>
            {!setup.project.trim() && <p className="small">Name a project to start, or fill in the demo one.</p>}
          </form>
        </main>
      )}

      {phase !== "setup" && (
        <main className="wrap iv-room">
          <ol className="iv-ticks" aria-label="Interview progress">
            {r.plan.map((q, i) => (
              <li
                key={q.id}
                data-s={i < cursor || (phase === "done" && i === cursor) ? "done" : i === cursor ? "now" : "next"}
                title={SECTION_LABEL[q.section]}
              >
                <span>{SECTION_LABEL[q.section]}</span>
              </li>
            ))}
          </ol>

          <div className="iv-stage">
            <figure className="iv-orb">
              <BlobStage state={agent} signal={signal} />
              <figcaption>
                <span className="iv-agent">{AGENT}</span>
                <span className="orb-state" aria-live="polite">
                  {phase === "done" ? "Finished" : CAPTION[agent]}
                </span>
                {phase === "live" && agent === "listening" && r.voiceIn && (
                  <span className="small">{micOn ? "Pause for two seconds when you're done." : "Mic paused. Type below."}</span>
                )}
              </figcaption>
            </figure>

            <section className="iv-log" aria-label="Transcript">
              <ol ref={log} aria-live="polite" tabIndex={0}>
                {turns.map((t) => (
                  <li key={t.id} data-r={t.role}>
                    <span className="iv-who">{t.role === "interviewer" ? AGENT : "You"}</span>
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
                  <button type="button" onClick={doneAnswering} disabled={agent !== "listening" || !interim}>
                    Done answering
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => void endAnswer(`${heard()}`.trim(), true)}
                  disabled={agent !== "listening"}
                >
                  Next question
                </button>
                <button type="button" className="iv-end" onClick={() => void finish(null)}>
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
                />
                <button type="submit" disabled={!typed.trim() || agent !== "listening"}>
                  Send
                </button>
              </form>
            </div>
          )}

          {phase === "done" && (
            <Notes turns={turns} plan={r.plan} setup={r.setup} seconds={elapsed} onAgain={() => setPhase("setup")} />
          )}
        </main>
      )}
    </div>
  );
}

// ---------------- notes ----------------

function Notes({
  turns,
  plan,
  setup,
  seconds,
  onAgain,
}: {
  turns: Turn[];
  plan: Question[];
  setup: Setup;
  seconds: number;
  onAgain: () => void;
}) {
  const rows = plan
    .map((q) => {
      const answers = turns.filter((t) => t.role === "candidate" && t.qid === q.id);
      const asked = turns.some((t) => t.role === "interviewer" && t.qid === q.id);
      const followup = turns.find((t) => t.role === "interviewer" && t.qid === q.id && t.kind !== "main")?.kind;
      const text = answers.map((a) => a.text).join(" ");
      const spokenMs = answers.reduce((n, a) => n + (a.start && a.end ? a.end - a.start : 0), 0);
      const spokenWords = answers.filter((a) => a.start).reduce((n, a) => n + words(a.text), 0);
      return {
        q,
        asked,
        followup,
        words: words(text),
        fillers: fillerCount(text),
        wpm: spokenMs > 4000 ? Math.round(spokenWords / (spokenMs / 60000)) : null,
      };
    })
    .filter((x) => x.asked);

  const answered = rows.filter((x) => x.words > 0).length;
  const totalWords = rows.reduce((n, x) => n + x.words, 0);
  const fillers = rows.reduce((n, x) => n + x.fillers, 0);
  const paces = rows.map((x) => x.wpm).filter((x): x is number => x !== null);
  const pace = paces.length ? Math.round(paces.reduce((a, b) => a + b, 0) / paces.length) : null;

  const download = () => {
    const lines = turns.map((t) => `${t.role === "interviewer" ? AGENT : "You"}: ${t.text}`);
    const file = new Blob([lines.join("\n\n") + "\n"], { type: "text/plain" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(file);
    a.download = "interview-transcript.txt";
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <section className="iv-notes" aria-labelledby="iv-notes-h">
      <h2 className="h3" id="iv-notes-h">
        Your notes
      </h2>
      <p className="small">
        Counts, not a grade. They come from the transcript with plain code, and nothing here goes into an assessment
        score.
      </p>
      <dl className="iv-stats">
        <div>
          <dt>Time</dt>
          <dd>{clock(seconds)}</dd>
        </div>
        <div>
          <dt>Questions answered</dt>
          <dd>
            {answered}
            <span className="muted"> / {plan.length}</span>
          </dd>
        </div>
        <div>
          <dt>Words spoken or typed</dt>
          <dd>{totalWords}</dd>
        </div>
        <div>
          <dt>Speaking pace</dt>
          <dd>{pace ? `${pace} wpm` : "n/a"}</dd>
        </div>
        <div>
          <dt>Filler words</dt>
          <dd>{fillers}</dd>
        </div>
      </dl>

      <ol className="iv-qs">
        {rows.map((x) => (
          <li key={x.q.id}>
            <span className="small">
              {SECTION_LABEL[x.q.section]}, {x.q.competency}
            </span>
            <p>{fill(x.q.text, setup)}</p>
            <p className="small">
              {x.words === 0
                ? "Skipped."
                : `${x.words} words${x.wpm ? `, ${x.wpm} wpm` : ""}${x.fillers ? `, ${x.fillers} filler words` : ""}.`}{" "}
              {x.followup === "simpler" && "Short first answer, so it got an easier follow-up."}
              {x.followup === "deeper" && "Detailed answer, so it got a harder follow-up."}
            </p>
          </li>
        ))}
      </ol>

      <div className="iv-buttons">
        <button type="button" onClick={download}>
          Download transcript
        </button>
        <button type="button" onClick={onAgain}>
          Practise again
        </button>
      </div>
    </section>
  );
}
