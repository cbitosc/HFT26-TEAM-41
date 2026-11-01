"use client";

// Trail Map (F4): the task's functions grouped by file (React Flow), the candidate's path
// through them replayed with a scrubber, dwell as heat, and report-only metric cards.
// Layout idea from showcase/components/TrailMap.tsx; the data comes from GET .../trail.
import { Background, Controls, MarkerType, Position, ReactFlow, type Edge, type Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useEffect, useMemo, useState } from "react";
import { api, ApiError, type TaskTrail } from "@/lib/api";
import { KeyForm, readKey, saveKey } from "./RecruiterKey";

const COLUMNS = 4;
const COL_WIDTH = 280;
const ROW_HEIGHT = 46;
const GROUP_PAD = 36;
const PLAY_STEPS = 300; // a replay takes PLAY_STEPS ticks
const TICK_MS = 50;

function clock(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000));
  return `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, "0")}s`;
}

const FOUND: Record<TaskTrail["metrics"]["found"], string> = {
  independent: "Independently",
  after_hint: "Within 2 min of a hint",
  not_found: "Not reached",
};

function Metrics({ trail }: { trail: TaskTrail }) {
  const m = trail.metrics;
  const cards: [string, string][] = [
    ["Time to target", m.time_to_target_ms === null ? "never" : clock(m.time_to_target_ms)],
    ["Off-path time before it", clock(m.off_path_ms)],
    ["Target found", FOUND[m.found]],
    ["Edit precision", m.edit_precision === null ? "no edits" : `${Math.round(m.edit_precision * 100)}%`],
    ["Lines changed", String(m.lines_changed)],
    ["Functions visited", String(m.functions_visited)],
    ["Hints", String(m.hints)],
  ];
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4" data-testid="trail-metrics">
      {cards.map(([label, value]) => (
        <div key={label} className="rounded-lg border border-gray-200 p-3">
          <div className="text-xs text-gray-500">{label}</div>
          <div className="mt-1 text-lg font-semibold tabular-nums">{value}</div>
        </div>
      ))}
    </div>
  );
}

/** Dwell per node up to `t` (visits clipped at t). */
function dwellAt(trail: TaskTrail, t: number): Record<string, number> {
  const out: Record<string, number> = {};
  for (const v of trail.visits) {
    if (v.start_ms >= t) break;
    out[v.node] = (out[v.node] ?? 0) + Math.min(v.end_ms, t) - v.start_ms;
  }
  return out;
}

function layout(trail: TaskTrail, t: number): { nodes: Node[]; edges: Edge[] } {
  const visitedIds = new Set(trail.visits.map((v) => v.node));
  const editedIds = new Set(trail.edits.map((e) => e.node));
  // Functions, plus a file's "(module)" node only when the candidate was there.
  const shown = trail.nodes.filter((n) => n.id.includes("::") || visitedIds.has(n.id) || editedIds.has(n.id));
  const files = [...new Set(shown.map((n) => n.file))].sort();
  const dwell = dwellAt(trail, t);
  const maxDwell = Math.max(1, ...Object.values(dwell));
  const current = [...trail.visits].reverse().find((v) => v.start_ms <= t && t <= v.end_ms + 1000)?.node;

  const nodes: Node[] = [];
  const rowHeights: number[] = [];
  files.forEach((file, i) => {
    const row = Math.floor(i / COLUMNS);
    const members = shown.filter((n) => n.file === file);
    rowHeights[row] = Math.max(rowHeights[row] ?? 0, GROUP_PAD + members.length * ROW_HEIGHT + 8);
  });
  files.forEach((file, i) => {
    const row = Math.floor(i / COLUMNS);
    const y = rowHeights.slice(0, row).reduce((a, b) => a + b + 40, 0);
    const members = shown.filter((n) => n.file === file);
    nodes.push({
      id: `file:${file}`,
      type: "group",
      position: { x: (i % COLUMNS) * (COL_WIDTH + 40), y },
      data: { label: file },
      style: { width: COL_WIDTH, height: GROUP_PAD + members.length * ROW_HEIGHT + 8, background: "#f9fafb", borderColor: "#e5e7eb" },
    });
    nodes.push({
      id: `label:${file}`,
      parentId: `file:${file}`,
      position: { x: 10, y: 8 },
      data: { label: file },
      draggable: false,
      selectable: false,
      style: { border: "none", background: "transparent", padding: 0, fontSize: 12, fontWeight: 600, width: COL_WIDTH - 20, textAlign: "left" },
    });
    members.forEach((n, j) => {
      const heat = (dwell[n.id] ?? 0) / maxDwell;
      nodes.push({
        id: n.id,
        parentId: `file:${file}`,
        extent: "parent",
        position: { x: 10, y: GROUP_PAD + j * ROW_HEIGHT },
        // Calls and the trail leave from the right and arrive on the left of a function.
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
        data: { label: `${n.name}${n.target ? "  ◎ target" : ""}` },
        style: {
          width: COL_WIDTH - 20,
          fontSize: 12,
          padding: "6px 8px",
          textAlign: "left",
          background: `rgba(239, 68, 68, ${(heat * 0.55).toFixed(3)})`,
          border: n.target ? "2px solid #2563eb" : "1px solid #d1d5db",
          boxShadow: n.id === current ? "0 0 0 3px #f59e0b" : undefined,
        },
      });
    });
  });

  const ids = new Set(shown.map((n) => n.id));
  const edges: Edge[] = trail.edges
    .filter(([a, b]) => ids.has(a) && ids.has(b))
    .map(([a, b]) => ({ id: `call:${a}->${b}`, source: a, target: b, style: { stroke: "#d1d5db" } }));
  const reached = trail.visits.filter((v) => v.start_ms <= t);
  reached.slice(1).forEach((v, i) => {
    const from = reached[i].node;
    if (!ids.has(from) || !ids.has(v.node)) return;
    const color = v.after_hint ? "#ea580c" : "#2563eb";
    edges.push({
      id: `trail:${i}`,
      source: from,
      target: v.node,
      animated: true,
      zIndex: 10,
      markerEnd: { type: MarkerType.ArrowClosed, color },
      style: { stroke: color, strokeWidth: 2 },
    });
  });
  return { nodes, edges };
}

function TaskMap({ trail }: { trail: TaskTrail }) {
  const start = trail.first_ms ?? 0;
  const end = trail.last_ms ?? start;
  const [t, setT] = useState(end);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    if (!playing) return;
    const step = Math.max(1, (end - start) / PLAY_STEPS);
    const timer = setInterval(() => {
      setT((prev) => {
        const next = prev + step;
        if (next >= end) {
          setPlaying(false);
          return end;
        }
        return next;
      });
    }, TICK_MS);
    return () => clearInterval(timer);
  }, [playing, start, end]);

  const { nodes, edges } = useMemo(() => layout(trail, t), [trail, t]);

  if (trail.visits.length === 0) {
    return (
      <div className="space-y-4">
        <Metrics trail={trail} />
        <p className="text-sm text-gray-500" data-testid="trail-empty">
          No editor activity was recorded for this task.
        </p>
      </div>
    );
  }

  const play = () => {
    if (t >= end) setT(start);
    setPlaying((p) => !p);
  };
  return (
    <div className="space-y-4">
      <Metrics trail={trail} />
      <div className="flex items-center gap-3">
        <button
          onClick={play}
          className="w-20 rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white"
          data-testid="trail-play"
        >
          {playing ? "Pause" : "Play"}
        </button>
        <div className="relative flex-1">
          <input
            type="range"
            min={start}
            max={end}
            value={t}
            onChange={(e) => {
              setPlaying(false);
              setT(Number(e.target.value));
            }}
            className="w-full"
            aria-label="Replay time"
            data-testid="trail-scrubber"
          />
          {trail.hints.map((h) => (
            <span
              key={h.ts}
              title={`Hint, level ${h.level}${h.blocked ? " (nudge)" : ""}`}
              className="absolute -top-1 h-3 w-0.5 bg-orange-600"
              style={{ left: `${((h.ts - start) / Math.max(1, end - start)) * 100}%` }}
            />
          ))}
        </div>
        <span className="w-20 text-right text-sm tabular-nums text-gray-600">{clock(t - start)}</span>
      </div>
      <div className="trail-map h-[560px] rounded-lg border border-gray-200" data-testid="trail-map">
        <ReactFlow nodes={nodes} edges={edges} fitView nodesConnectable={false} proOptions={{ hideAttribution: false }}>
          <Background />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
      <p className="text-xs text-gray-500">
        Blue outline: target symbol. Red fill: time spent (up to the scrubber). Moving blue arrows: the path before any
        hint; orange: after a hint (orange ticks on the scrubber). Grey lines: calls. Report-only, not part of the
        score.
      </p>
    </div>
  );
}

export default function TrailTab({ sessionId }: { sessionId: string }) {
  const [key, setKey] = useState(readKey);
  const [tasks, setTasks] = useState<TaskTrail[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState(0);

  useEffect(() => {
    if (!key) return;
    let cancelled = false;
    api
      .getTrail(sessionId, key)
      .then((out) => {
        if (!cancelled) {
          setTasks(out.tasks);
          setError(null);
        }
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          saveKey("");
          setKey("");
          setError("That recruiter key was not accepted.");
        } else if (err instanceof ApiError && err.status === 503) {
          setError("The server has no RECRUITER_API_KEY set.");
        } else {
          setError("Could not load the Trail Map.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId, key]);

  if (!key) {
    return (
      <KeyForm
        error={error}
        onKey={(next) => {
          setError(null);
          setKey(next);
        }}
      />
    );
  }
  if (error) return <p className="text-sm text-red-700">{error}</p>;
  if (!tasks) return <p className="text-sm text-gray-500">Loading the Trail Map…</p>;

  const trail = tasks[active];
  return (
    <div className="space-y-4">
      <nav className="flex gap-2">
        {tasks.map((task, i) => (
          <button
            key={task.task_id}
            onClick={() => setActive(i)}
            className={`rounded px-3 py-1 text-sm ${i === active ? "bg-gray-900 text-white" : "bg-gray-100 text-gray-700"}`}
          >
            {i + 1}. {task.kind === "dsa" ? "DSA" : "Domain"} task
          </button>
        ))}
      </nav>
      <TaskMap key={trail.task_id} trail={trail} />
    </div>
  );
}
