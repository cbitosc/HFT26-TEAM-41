"use client";

import OracleOrb, { type OrbSignal, type OrbState } from "../OracleOrb";

export type AgentState = OrbState;

/** Shared, mutable signal the page writes and the orb reads every frame. */
export type BlobSignal = OrbSignal;

// The interviewer's orb: the shared WebGL oracle (components/OracleOrb.tsx).
export default function Blob({ state, signal }: { state: AgentState; signal: BlobSignal }) {
  return <OracleOrb state={state} signal={signal} className="iv-blob" />;
}
