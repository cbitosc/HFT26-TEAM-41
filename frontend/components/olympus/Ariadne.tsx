"use client";
// Ariadne: the Labyrinth's chat guide, docked bottom-right. Demo replies are matched by
// keyword and streamed; a live session would route through the guarded assistant
// endpoint (backend/llm only — the browser never calls a model directly).
import { useEffect, useRef, useState } from "react";
import Engraving from "./Engraving";
import { IconSend, IconThread, IconX } from "./Icons";
import { ARIADNE_SUGGESTIONS, ariadneReply } from "@/lib/olympus/demo";
import { gsap } from "@/lib/olympus/motion";

type Msg = { from: "you" | "ariadne"; text: string };

export default function Ariadne({ onAsk }: { onAsk?: () => void }) {
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([
    { from: "ariadne", text: "I hold the thread through this labyrinth. Ask me how the code flows, where a bug might hide, or how to prove it — I'll point the way, not walk it for you." },
  ]);
  const [draft, setDraft] = useState("");
  const [streaming, setStreaming] = useState(false);
  const panel = useRef<HTMLDivElement>(null);
  const list = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!panel.current) return;
    if (open) gsap.fromTo(panel.current, { scale: 0.6, opacity: 0, y: 30 }, { scale: 1, opacity: 1, y: 0, duration: 0.7, ease: "expo.out" });
  }, [open]);

  useEffect(() => {
    list.current?.scrollTo({ top: list.current.scrollHeight, behavior: "smooth" });
  }, [msgs]);

  const ask = (text: string) => {
    const q = text.trim();
    if (!q || streaming) return;
    onAsk?.();
    setDraft("");
    const reply = ariadneReply(q);
    setMsgs((m) => [...m, { from: "you", text: q }, { from: "ariadne", text: "" }]);
    setStreaming(true);
    let i = 0;
    window.setTimeout(() => {
      const id = window.setInterval(() => {
        i = Math.min(reply.length, i + 3);
        setMsgs((m) => [...m.slice(0, -1), { from: "ariadne", text: reply.slice(0, i) }]);
        if (i >= reply.length) {
          window.clearInterval(id);
          setStreaming(false);
        }
      }, 18);
    }, 700);
  };

  return (
    <div className="no-print fixed bottom-5 right-5 z-50 flex flex-col items-end gap-4">
      {open && (
        <div
          ref={panel}
          role="dialog"
          aria-label="Ariadne, repository guide"
          className="flex h-[min(600px,calc(100dvh-120px))] w-[min(400px,calc(100vw-40px))] origin-bottom-right flex-col overflow-hidden rounded-[24px] bg-[var(--parchment)] shadow-[0_40px_80px_-30px_rgba(6,10,34,0.55),inset_0_0_0_1px_var(--line-strong)]"
        >
          <header className="relative flex items-center gap-3 overflow-hidden bg-[var(--ink)] px-5 py-4 text-[var(--parchment)]">
            <span className="grid h-11 w-11 place-items-center overflow-hidden rounded-full bg-[var(--parchment)]">
              <Engraving name="muse-bust" className="w-9 text-[var(--ink)]" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="display text-[22px] leading-none">Ariadne</p>
              <p className="mt-1 flex items-center gap-1.5 text-[11.5px] opacity-75">
                <span className="pulse-dot !h-1.5 !w-1.5 text-[#8fd6b0]" /> Repository guide · guarded
              </p>
            </div>
            <button className="icon-btn !text-[var(--parchment)] !shadow-[inset_0_0_0_1px_rgba(7,11,38,0.25)]" onClick={() => setOpen(false)} aria-label="Close chat">
              <IconX size={16} />
            </button>
            <IconThread size={90} className="pointer-events-none absolute -right-4 -bottom-8 opacity-10" />
          </header>

          <div ref={list} className="scroll-y flex-1 space-y-3 p-4" aria-live="polite">
            {msgs.map((m, k) => (
              <div key={k} className={`rise flex ${m.from === "you" ? "justify-end" : "justify-start"}`}>
                <p
                  className="max-w-[85%] whitespace-pre-wrap rounded-[18px] px-4 py-2.5 text-[14px] leading-relaxed"
                  style={
                    m.from === "you"
                      ? { background: "var(--ink)", color: "var(--parchment)", borderBottomRightRadius: 6 }
                      : { background: "rgba(13,19,56,0.9)", boxShadow: "inset 0 0 0 1px var(--line)", borderBottomLeftRadius: 6 }
                  }
                >
                  {m.text ? <InlineCode text={m.text} /> : <TypingDots />}
                </p>
              </div>
            ))}
          </div>

          <div className="border-t border-[var(--line)] p-3">
            {msgs.length < 3 && (
              <div className="mb-3 flex flex-wrap gap-1.5">
                {ARIADNE_SUGGESTIONS.map((s) => (
                  <button key={s} onClick={() => ask(s)} className="chip !h-auto !py-1.5 text-left !text-[12px] !whitespace-normal transition-colors hover:bg-[rgba(35,55,165,0.06)]">
                    {s}
                  </button>
                ))}
              </div>
            )}
            <form
              className="flex items-center gap-2 rounded-full bg-[rgba(13,19,56,0.9)] p-1.5 pl-4 shadow-[inset_0_0_0_1px_var(--line-strong)]"
              onSubmit={(e) => {
                e.preventDefault();
                ask(draft);
              }}
            >
              <input
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="Ask Ariadne about the code…"
                aria-label="Message Ariadne"
                className="min-w-0 flex-1 bg-transparent text-[14px] outline-none placeholder:text-[var(--text-3)]"
              />
              <button type="submit" disabled={!draft.trim() || streaming} className="grid h-9 w-9 place-items-center rounded-full bg-[var(--ink)] text-[var(--parchment)] transition-transform hover:scale-105 disabled:opacity-40" aria-label="Send">
                <IconSend size={15} />
              </button>
            </form>
          </div>
        </div>
      )}

      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-label={open ? "Close Ariadne" : "Ask Ariadne, the repository guide"}
        data-cursor={open ? "" : "Ask"}
        className="group relative grid h-16 w-16 place-items-center rounded-full bg-[var(--ink)] text-[var(--parchment)] shadow-[0_20px_40px_-12px_rgba(35,55,165,0.6)] transition-transform duration-500 hover:scale-105"
      >
        {!open && <span className="absolute inset-0 animate-ping rounded-full bg-[var(--ink)] opacity-20" />}
        <span className="relative transition-transform duration-700 group-hover:rotate-[200deg]">{open ? <IconX size={22} /> : <IconThread size={26} />}</span>
      </button>
    </div>
  );
}

function TypingDots() {
  return (
    <span className="inline-flex items-center gap-1 py-1" aria-label="Ariadne is typing">
      {[0, 1, 2].map((i) => (
        <span key={i} className="h-1.5 w-1.5 animate-bounce rounded-full bg-[var(--ink)]" style={{ animationDelay: `${i * 0.15}s` }} />
      ))}
    </span>
  );
}

/** Renders `code` spans in replies. */
function InlineCode({ text }: { text: string }) {
  return (
    <>
      {text.split(/(`[^`]+`)/g).map((part, i) =>
        part.startsWith("`") && part.endsWith("`") && part.length > 1 ? (
          <code key={i} className="mono rounded bg-[rgba(35,55,165,0.1)] px-1 text-[12.5px] text-[var(--ink-deep)]">
            {part.slice(1, -1)}
          </code>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </>
  );
}
