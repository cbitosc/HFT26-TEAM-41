"use client";

import { useEffect, useRef, useState } from "react";
import OracleOrb, { type OrbSignal, type OrbState } from "./OracleOrb";
import { AGENT } from "@/lib/site";

// The oracle on the home page, cycling through its four states with a simulated
// volume so the reader can see each one.
const STATES: OrbState[] = ["idle", "listening", "thinking", "speaking"];
const CAPTION: Record<OrbState, string> = {
  idle: "Idle",
  listening: "Listening",
  thinking: "Thinking",
  speaking: "Speaking",
};

export default function Orb() {
  const [state, setState] = useState<OrbState>("idle");
  const signal = useRef<OrbSignal>({ level: 0, pulses: 0 }).current;

  useEffect(() => {
    const start = performance.now();
    let last = -1;
    const id = setInterval(() => {
      const t = (performance.now() - start) / 1000;
      const i = Math.floor(t / 3.2) % STATES.length;
      if (i !== last) {
        last = i;
        setState(STATES[i]);
      }
      const st = STATES[i];
      signal.level =
        st === "speaking" ? 0.55 + 0.45 * Math.abs(Math.sin(t * 7.1) * Math.sin(t * 2.3))
        : st === "listening" ? 0.25 + 0.3 * Math.abs(Math.sin(t * 5.3 + Math.sin(t * 1.7)))
        : 0.04;
      if (st === "speaking" && Math.sin(t * 7.1) > 0.97) signal.pulses += 1;
    }, 50);
    return () => clearInterval(id);
  }, [signal]);

  return (
    <figure className="orb">
      <OracleOrb state={state} signal={signal} className="orb-canvas" />
      <figcaption>
        <span className="orb-name">{AGENT}</span>
        <span className="orb-state">{CAPTION[state]}</span>
        <span className="small">Simulated audio level. The real orb follows the mic or the TTS playback.</span>
      </figcaption>
    </figure>
  );
}
