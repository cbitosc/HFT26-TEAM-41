"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { animate, motion, useInView, useMotionValue, useMotionValueEvent, useReducedMotion } from "motion/react";
import Chip from "./Chip";
import { Label, Words } from "./fx";

// Nodes and edges are the real functions and calls of seeds/py-fastapi-expenses.
// The two candidate trails are SAMPLE data: the Trail Map builder is P4.4.

type Node = { id: string; fn: string; file: string; x: number; y: number };

const NODES: Node[] = [
  { id: "r.list", fn: "list_expenses", file: "routes.py", x: 110, y: 150 },
  { id: "r.create", fn: "create_expense", file: "routes.py", x: 110, y: 300 },
  { id: "r.report", fn: "get_monthly_report", file: "routes.py", x: 110, y: 440 },
  { id: "a.user", fn: "get_current_user", file: "auth.py", x: 390, y: 50 },
  { id: "s.list", fn: "list_expenses", file: "services.py", x: 390, y: 170 },
  { id: "s.filters", fn: "apply_filters", file: "services.py", x: 600, y: 250 },
  { id: "s.sorting", fn: "apply_sorting", file: "services.py", x: 600, y: 330 },
  { id: "s.create", fn: "create_expense", file: "services.py", x: 390, y: 320 },
  { id: "s.monthly", fn: "monthly_report", file: "services.py", x: 390, y: 450 },
  { id: "s.compute", fn: "compute_monthly_report", file: "services.py", x: 640, y: 470 },
  { id: "u.paginate", fn: "paginate", file: "utils.py", x: 640, y: 150 },
  { id: "u.bounds", fn: "month_bounds", file: "utils.py", x: 890, y: 470 },
  { id: "p.find", fn: "find_user_by_token", file: "repo.py", x: 670, y: 50 },
  { id: "p.of", fn: "expenses_of", file: "repo.py", x: 890, y: 250 },
  { id: "p.insert", fn: "insert_expense", file: "repo.py", x: 890, y: 340 },
];

const EDGES: [string, string][] = [
  ["r.list", "a.user"], ["r.create", "a.user"], ["r.report", "a.user"], ["a.user", "p.find"],
  ["r.list", "s.list"], ["s.list", "s.filters"], ["s.list", "s.sorting"], ["s.list", "u.paginate"],
  ["s.list", "p.of"], ["r.create", "s.create"], ["s.create", "p.insert"],
  ["r.report", "s.monthly"], ["s.monthly", "s.compute"], ["s.compute", "u.bounds"],
];

const BUG = "u.paginate";

type Visit = { id: string; min: number };
type Trail = {
  key: "A" | "B";
  label: string;
  visits: Visit[];
  stats: [string, string][];
};

const TRAILS: Trail[] = [
  {
    key: "A",
    label: "Candidate A",
    visits: [
      { id: "r.list", min: 0.5 }, { id: "s.list", min: 1.0 }, { id: "u.paginate", min: 4.0 },
    ],
    stats: [["Final score", "100"], ["Time to bug", "1 m 30 s"], ["Off-path time", "0 m"], ["Functions opened", "3"], ["Lines edited", "1"]],
  },
  {
    key: "B",
    label: "Candidate B",
    visits: [
      { id: "r.list", min: 1.5 }, { id: "a.user", min: 2.0 }, { id: "p.find", min: 1.5 },
      { id: "s.list", min: 1.0 }, { id: "s.filters", min: 3.0 }, { id: "s.sorting", min: 2.5 },
      { id: "p.of", min: 2.0 }, { id: "s.list", min: 1.0 }, { id: "u.paginate", min: 5.5 },
    ],
    stats: [["Final score", "100"], ["Time to bug", "14 m 30 s"], ["Off-path time", "11 m"], ["Functions opened", "8"], ["Lines edited", "6"]],
  },
];

const byId = Object.fromEntries(NODES.map((n) => [n.id, n]));

function curve(a: Node, b: Node) {
  const mx = (a.x + b.x) / 2;
  return `C ${mx} ${a.y} ${mx} ${b.y} ${b.x} ${b.y}`;
}

function trailPath(visits: Visit[]) {
  const pts = visits.map((v) => byId[v.id]);
  return pts.reduce((d, p, i) => (i === 0 ? `M ${p.x} ${p.y}` : `${d} ${curve(pts[i - 1], p)}`), "");
}

export default function TrailMap() {
  const [which, setWhich] = useState<"A" | "B">("B");
  const [run, setRun] = useState(0);
  const trail = TRAILS.find((t) => t.key === which)!;
  const box = useRef<HTMLDivElement>(null);
  const pathRef = useRef<SVGPathElement>(null);
  const seen = useInView(box, { once: true, amount: 0.35 });
  const reduce = useReducedMotion();
  const progress = useMotionValue(0);
  const [dot, setDot] = useState<{ x: number; y: number } | null>(null);
  const [reached, setReached] = useState(0);

  const d = useMemo(() => trailPath(trail.visits), [trail]);
  const total = trail.visits.reduce((s, v) => s + v.min, 0);

  // Fraction of the path length at which each visit starts (by segment count).
  const marks = useMemo(() => trail.visits.map((_, i) => (trail.visits.length === 1 ? 0 : i / (trail.visits.length - 1))), [trail]);

  useMotionValueEvent(progress, "change", (v) => {
    const p = pathRef.current;
    if (!p) return;
    const len = p.getTotalLength();
    const pt = p.getPointAtLength(v * len);
    setDot({ x: pt.x, y: pt.y });
    setReached(marks.filter((m) => m <= v + 0.001).length);
  });

  useEffect(() => {
    if (!seen) return;
    if (reduce) {
      progress.set(1);
      return;
    }
    progress.set(0);
    const c = animate(progress, 1, { duration: 1.2 + trail.visits.length * 0.55, ease: "easeInOut" });
    return () => c.stop();
  }, [seen, reduce, trail, run, progress]);

  const visited = trail.visits.slice(0, reached);
  const dwell: Record<string, number> = {};
  visited.forEach((v) => (dwell[v.id] = (dwell[v.id] ?? 0) + v.min));

  return (
    <section className="section trail" id="trail">
      <div className="wrap">
        <div className="grid trail-top">
          <div className="trail-intro">
            <Label n={2}>Ariadne&apos;s thread</Label>
            <Words className="h2" text="Same score. *Different* engineers." />
            <p className="lede">
              Theseus found the Minotaur by following a thread. The Debug Trail Map lays that thread through the
              candidate&apos;s session.
            </p>
            <p>
              Both candidates fixed the pagination bug and scored 100. The map shows how: which functions they opened,
              in what order, and for how long. A went straight from the route to the bug. B read auth, filters and
              sorting first. Report-only: it never changes the score.
            </p>
            <div className="trail-status">
              <Chip s="planned">Planned: P4.4 builder, P4.5 replay</Chip>
              <span className="small">Real call graph from the seed repo. Candidate trails are sample data.</span>
            </div>
          </div>
        </div>

        <div className="trail-stage" ref={box}>
          <div className="trail-controls" role="tablist" aria-label="Candidate">
            {TRAILS.map((t) => (
              <button
                key={t.key}
                role="tab"
                aria-selected={which === t.key}
                className={which === t.key ? "on" : ""}
                onClick={() => {
                  setWhich(t.key);
                  setRun((r) => r + 1);
                }}
              >
                {t.label}
              </button>
            ))}
            <button className="trail-replay" onClick={() => setRun((r) => r + 1)}>
              Replay
            </button>
          </div>

          <div className="trail-body">
            <div className="trail-svg-wrap">
              <svg viewBox="0 0 1000 520" className="trail-svg" role="img" aria-label={`${trail.label}'s path through the code`}>
                <defs>
                  <filter id="thread-glow" x="-10%" y="-10%" width="120%" height="120%">
                    <feGaussianBlur stdDeviation="3" result="b" />
                    <feMerge>
                      <feMergeNode in="b" />
                      <feMergeNode in="SourceGraphic" />
                    </feMerge>
                  </filter>
                  <clipPath id="maze-clip">
                    <rect x="0" y="0" width="1000" height="520" />
                  </clipPath>
                </defs>
                <g className="t-maze" clipPath="url(#maze-clip)" aria-hidden>
                  {[60, 100, 140, 180, 220, 260, 300].map((r, i) => (
                    <circle key={r} cx={640} cy={150} r={r} strokeDasharray={`${180 + i * 40} 26`} transform={`rotate(${i * 47} 640 150)`} />
                  ))}
                </g>
                {EDGES.map(([a, b]) => {
                  const A = byId[a], B = byId[b];
                  return <path key={a + b} d={`M ${A.x} ${A.y} ${curve(A, B)}`} className="t-edge" />;
                })}
                <motion.path
                  key={which + run}
                  ref={pathRef}
                  d={d}
                  className="t-path"
                  style={{ pathLength: progress }}
                  filter="url(#thread-glow)"
                />
                {NODES.map((n) => {
                  const w = dwell[n.id];
                  return (
                    <g key={n.id} className={`t-node ${w ? "on" : ""} ${n.id === BUG ? "bug" : ""}`}>
                      {w ? (
                        <motion.circle
                          cx={n.x}
                          cy={n.y}
                          initial={{ r: 0 }}
                          animate={{ r: 9 + w * 3.2 }}
                          transition={{ type: "spring", stiffness: 200, damping: 20 }}
                          className="t-dwell"
                        />
                      ) : null}
                      {n.id === BUG ? (
                        <g className="t-bull">
                          <mask id="bull-sil" style={{ maskType: "alpha" }}>
                            <image href="/greek/bull-sil.webp" x={n.x - 34} y={n.y - 40} width={68} height={70} />
                          </mask>
                          <mask id="bull-ink" style={{ maskType: "alpha" }}>
                            <image href="/greek/bull-ink.webp" x={n.x - 34} y={n.y - 40} width={68} height={70} />
                          </mask>
                          <rect x={n.x - 34} y={n.y - 40} width={68} height={70} mask="url(#bull-sil)" className="t-bull-sil" />
                          <rect x={n.x - 34} y={n.y - 40} width={68} height={70} mask="url(#bull-ink)" className="t-bull-ink" />
                        </g>
                      ) : (
                        <circle cx={n.x} cy={n.y} r={6} className="t-dot" />
                      )}
                      <text x={n.x} y={n.y + (n.id === BUG ? 46 : 28)} textAnchor="middle" className="t-fn">{n.id === BUG ? `${n.fn}: the Minotaur` : n.fn}</text>
                      <text x={n.x} y={n.y + (n.id === BUG ? 62 : 44)} textAnchor="middle" className="t-file">{n.file}</text>
                    </g>
                  );
                })}
                {dot && <circle cx={dot.x} cy={dot.y} r={7} className="t-head" />}
              </svg>
            </div>

            <dl className="trail-stats">
              {trail.stats.map(([k, v]) => (
                <div key={k}>
                  <dt>{k}</dt>
                  <dd>{v}</dd>
                </div>
              ))}
            </dl>
          </div>

          <div className="trail-time" aria-hidden>
            {trail.visits.map((v, i) => (
              <span
                key={i}
                style={{ flexGrow: v.min, opacity: i < reached ? 1 : 0.15 }}
                className={v.id === BUG ? "bug" : v.id.startsWith("s.list") || v.id === "r.list" ? "path" : "off"}
                title={`${byId[v.id].fn}: ${v.min} min`}
              />
            ))}
            <em>{total} min on the domain task</em>
          </div>
        </div>
      </div>
    </section>
  );
}
