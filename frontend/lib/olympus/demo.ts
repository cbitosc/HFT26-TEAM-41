// Demo content for the themed journey. In a live assessment these come from the backend
// (profiler, builders, hint endpoint, interviewer); here they are fixed so the flow works
// without the stack. Nothing in this file is a reference solution or a hidden test.
import type { Profile } from "@/lib/types";
import type { Candidate, Journey, TaskOutcome } from "./journey";

export const DEMO_PROFILE: Profile = {
  domain: "backend",
  runtime: "python311",
  concepts: ["pagination", "caching", "auth", "reporting"],
  topics_solved: { arrays: 48, hashing: 35, two_pointers: 22, sliding_window: 14, trees: 19, graphs_bfs_dfs: 16, dp: 11 },
  allowed_topics: {
    novice: ["arrays", "hashing", "two_pointers", "sliding_window", "trees", "dp"],
    adept: ["arrays", "hashing", "two_pointers", "sliding_window", "trees", "graphs_bfs_dfs", "dp"],
    master: ["arrays", "hashing"],
  },
  suggested_tier: "adept",
  tier_reason: "2 projects, 165 problems solved and an adept topic (graphs) → adept.",
  unsupported_notes: [],
  sources: { domain: "rules", runtime: "rules", concepts: "rules" },
};

export function displayName(c: Candidate | null): string {
  return c?.name.trim() || "Wanderer";
}

export function firstName(c: Candidate | null): string {
  return displayName(c).split(/\s+/)[0];
}

export function initials(c: Candidate | null): string {
  return displayName(c)
    .split(/\s+/)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? "")
    .join("");
}

/** The handles and stack the assessment was forged from, for the "forged from" chips. */
export function forgedFrom(j: Journey): string[] {
  const c = j.candidate;
  const p = j.profile ?? DEMO_PROFILE;
  const out: string[] = [];
  if (c?.github) out.push(`GitHub · ${handleOf(c.github)}`);
  if (c?.leetcode) out.push(`LeetCode · ${handleOf(c.leetcode)}`);
  if (c?.codeforces) out.push(`Codeforces · ${handleOf(c.codeforces)}`);
  if (c?.resumeName) out.push(`Résumé · ${c.resumeName}`);
  out.push(...(c?.stack.length ? c.stack : ["FastAPI", "PostgreSQL", "Redis"]));
  out.push(...p.concepts.slice(0, 3));
  return out;
}

export function handleOf(value: string): string {
  const trimmed = value.trim().replace(/\/+$/, "");
  return trimmed.split("/").pop() || trimmed;
}

// ---------------------------------------------------------------------------------------
// Trials of Athena
// ---------------------------------------------------------------------------------------

export type DemoFile = { path: string; content: string; readOnly?: boolean };
export type DemoTask = {
  id: string;
  kind: "domain" | "dsa";
  title: string;
  subtitle: string;
  statement: string;
  files: DemoFile[];
  visibleTests: string[];
  hiddenCount: number;
  summary: string[];
  hints: [string, string, string];
  /** Simulated in the browser for the demo; a live session runs the tests in a sandbox. */
  check: (files: Record<string, string>) => boolean[];
};

const PAGINATE_STARTER = `"""Helpers shared by the expense routes."""
from dataclasses import dataclass
from typing import Sequence, TypeVar

T = TypeVar("T")


@dataclass
class Page:
    items: list
    page: int
    page_size: int
    total: int


def paginate(rows: Sequence[T], page: int, page_size: int) -> Page:
    """Return one page of rows. Pages are numbered from 1."""
    if page < 1 or page_size < 1:
        raise ValueError("page and page_size must be positive")
    offset = (page - 2) * page_size
    items = list(rows[offset : offset + page_size])
    return Page(items=items, page=page, page_size=page_size, total=len(rows))
`;

const ROUTES_EXCERPT = `from fastapi import APIRouter, Depends, Query

from .auth import current_user
from .repo import list_expenses
from .utils import paginate

router = APIRouter()


@router.get("/expenses")
def get_expenses(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user=Depends(current_user),
):
    rows = list_expenses(user.id)
    return paginate(rows, page, page_size)
`;

const PAGINATION_TESTS = `from app.utils import paginate

ROWS = list(range(1, 46))  # 45 expenses


def test_first_page_starts_at_first_row():
    assert paginate(ROWS, 1, 20).items == ROWS[:20]


def test_second_page_continues():
    assert paginate(ROWS, 2, 20).items[0] == 21


def test_total_is_reported():
    assert paginate(ROWS, 3, 20).total == 45
`;

const DSA_STARTER = `def longest_calm_streak(readings: str) -> int:
    """Return the length of the longest run of sensor readings in which
    no symbol repeats.

    >>> longest_calm_streak("abcabcbb")
    3
    """
    raise NotImplementedError
`;

export const TRIAL_TASKS: DemoTask[] = [
  {
    id: "domain",
    kind: "domain",
    title: "The Broken Ledger",
    subtitle: "Bug fix · your FastAPI expenses API",
    statement: `# The Broken Ledger

Your expenses service paginates \`GET /expenses\` with \`?page=\` and \`?page_size=\`.
Users report that **page 1 comes back empty** and every later page is one page behind.

Find the fault and repair it so each page returns the right rows, in order.

## What you can change
- \`app/utils.py\` — pagination helpers

## What is checked
- 3 visible tests in \`tests/test_pagination.py\` (run them any time)
- hidden tests cover the last page, empty pages and large page sizes

> Built from your stack: **FastAPI · PostgreSQL** and the *pagination* concept found in your repositories.
`,
    files: [
      { path: "app/utils.py", content: PAGINATE_STARTER },
      { path: "app/routes.py", content: ROUTES_EXCERPT, readOnly: true },
      { path: "tests/test_pagination.py", content: PAGINATION_TESTS, readOnly: true },
    ],
    visibleTests: ["test_first_page_starts_at_first_row", "test_second_page_continues", "test_total_is_reported"],
    hiddenCount: 8,
    summary: [
      "A bug, not a feature: pages are shifted by one page.",
      "One editable file — app/utils.py, function paginate().",
      "3 visible tests; 8 hidden ones probe boundaries (last page, empty page).",
      "Done when page p returns rows (p−1)·size … p·size−1.",
    ],
    hints: [
      "Read the docstring of paginate, then the first test. Where should page 1 begin?",
      "Look at how offset is computed — check it by hand for page = 1.",
      "For pages numbered from 1, the first row of page p sits at index (p − 1) × page_size.",
    ],
    check: (files) => {
      const code = files["app/utils.py"] ?? "";
      const fixed = /offset\s*=\s*\(\s*page\s*-\s*1\s*\)\s*\*\s*page_size/.test(code.replace(/#.*$/gm, ""));
      return [fixed, fixed, true];
    },
  },
  {
    id: "dsa",
    kind: "dsa",
    title: "The Calm Streak",
    subtitle: "Algorithms · sliding window · medium",
    statement: `# The Calm Streak

A sensor writes one symbol per tick. A *calm streak* is a run of consecutive readings in which
**no symbol repeats**. Return the length of the longest calm streak.

\`\`\`text
longest_calm_streak("abcabcbb")  ->  3      # "abc"
longest_calm_streak("bbbbb")     ->  1
longest_calm_streak("")          ->  0
\`\`\`

## Constraints
- \`0 ≤ len(readings) ≤ 5 · 10⁴\`
- readings may hold letters, digits, symbols and spaces

> Picked for you: you have solved **14 sliding-window** problems on LeetCode.
`,
    files: [{ path: "solution.py", content: DSA_STARTER }],
    visibleTests: ['"abcabcbb" → 3', '"bbbbb" → 1', '"pwwkew" → 3', '"" → 0', '" " → 1'],
    hiddenCount: 30,
    summary: [
      "Longest substring with all-distinct characters.",
      "Return a length, not the substring.",
      "Up to 50,000 characters — aim for O(n).",
      "Edge cases: empty input, all repeats, spaces count as symbols.",
    ],
    hints: [
      "Can you keep a window of readings that never contains a repeat?",
      "Grow the right edge each step; shrink the left edge while the new symbol is already inside.",
      "Remember where each symbol was last seen so the left edge can jump straight past it.",
    ],
    check: (files) => {
      const code = files["solution.py"] ?? "";
      const body = code.split('"""').pop() ?? "";
      const attempted = !/raise\s+NotImplementedError/.test(body) && /return/.test(body);
      const windowed = attempted && /(for|while)/.test(body) && /(set\(|dict\(|\{\}|in\s+\w+)/.test(body);
      return [windowed, windowed, windowed, attempted, windowed];
    },
  },
];

export type QuizQuestion = {
  id: string;
  basis: string; // which part of the candidate's record it came from
  prompt: string;
  code?: string;
  options: string[];
  answer: number;
};

export const QUIZ: QuizQuestion[] = [
  {
    id: "q1",
    basis: "Your repo · expense-tracker (FastAPI)",
    prompt: "A list endpoint loads 50 expenses, then reads `expense.category.name` for each one. Postgres logs show 51 queries. What is happening?",
    options: [
      "Connection pool exhaustion",
      "An N+1 query — eager-load or join the categories",
      "Missing index on expenses.id",
      "FastAPI serialises responses twice",
    ],
    answer: 1,
  },
  {
    id: "q2",
    basis: "Your stack · Redis",
    prompt: "Monthly reports are cached in Redis under `report:{user}:{month}`. A user adds an expense dated March 3. What keeps reports correct?",
    options: [
      "Nothing — the TTL will catch up eventually",
      "Flush the whole Redis database",
      "Delete `report:{user}:2026-03` when the expense is written",
      "Cache reports per request id instead",
    ],
    answer: 2,
  },
  {
    id: "q3",
    basis: "LeetCode · 14 sliding-window solves",
    prompt: "What is the time complexity of a two-pointer sliding window where each pointer only moves forward?",
    code: "for right in range(n):\n    while bad(window):\n        left += 1",
    options: ["O(n²)", "O(n log n)", "O(n)", "O(n·k) for alphabet size k"],
    answer: 2,
  },
  {
    id: "q4",
    basis: "Your repo · auth module",
    prompt: "Where should bearer-token validation live in a FastAPI service so every protected route enforces it?",
    options: [
      "In each route body, as the first line",
      "In a dependency (Depends) attached to the routes or router",
      "In a Pydantic validator on the response model",
      "In the Uvicorn access log hook",
    ],
    answer: 1,
  },
  {
    id: "q5",
    basis: "Codeforces · rating 1480",
    prompt: "You must answer 10⁵ range-sum queries on a static array of 10⁵ numbers. Which preparation fits?",
    options: ["Sort the array", "Prefix sums, O(1) per query", "A hash map of every range", "Recompute each sum, O(n) per query"],
    answer: 1,
  },
];

// ---------------------------------------------------------------------------------------
// The Labyrinth (code comprehension)
// ---------------------------------------------------------------------------------------

export const LABYRINTH_REPO = {
  owner: "olympus-labs",
  name: "hermes-courier",
  description: "A FastAPI dispatch service that assigns parcels to couriers by zone and distance.",
  stars: 128,
  language: "Python",
  branch: "main",
};

export const LABYRINTH_FILES: DemoFile[] = [
  {
    path: "README.md",
    content: `# hermes-courier

Dispatch service for same-day parcels.

- \`POST /dispatch\` assigns each waiting parcel to the nearest free courier in its zone
- \`GET /deliveries\` lists today's deliveries with courier names
- routes between zones are cached for 10 minutes

Run: \`uvicorn app.main:app --reload\`
`,
  },
  {
    path: "app/main.py",
    content: `from fastapi import FastAPI

from .routes import router

app = FastAPI(title="hermes-courier")
app.include_router(router)
`,
  },
  {
    path: "app/routes.py",
    content: `from fastapi import APIRouter

from . import dispatch, repo
from .cache import route_between

router = APIRouter()


@router.post("/dispatch")
def run_dispatch():
    parcels = repo.waiting_parcels()
    couriers = repo.free_couriers()
    return dispatch.assign(parcels, couriers)


@router.get("/deliveries")
def deliveries():
    return repo.list_deliveries()


@router.get("/route/{zone}/{origin}/{target}")
def route(zone: str, origin: str, target: str):
    return route_between(zone, origin, target)
`,
  },
  {
    path: "app/dispatch.py",
    content: `from dataclasses import dataclass


@dataclass
class Point:
    lat: float
    lon: float


def distance(a: Point, b: Point) -> float:
    """Manhattan distance on the city grid."""
    return abs(a.lat - b.lat) + abs(a.lon - b.lat)


def assign(parcels, couriers):
    """Give each parcel the nearest free courier in the same zone."""
    assignments = []
    taken = []
    for parcel in parcels:
        best = None
        for courier in couriers:
            if courier.id in taken:
                continue
            if courier.zone != parcel.zone:
                continue
            if best is None or distance(courier.pos, parcel.pos) < distance(best.pos, parcel.pos):
                best = courier
        if best is not None:
            taken.append(best.id)
            assignments.append((parcel.id, best.id))
    return assignments
`,
  },
  {
    path: "app/cache.py",
    content: `import time

from .maps import shortest_route

TTL_SECONDS = 600
_routes: dict = {}


def route_between(zone: str, origin: str, target: str):
    key = f"{origin}->{target}"
    entry = _routes.get(key)
    if entry and time.time() - entry["ts"] < TTL_SECONDS:
        return entry["route"]
    route = shortest_route(zone, origin, target)
    _routes[key] = {"ts": time.time(), "route": route}
    return route
`,
  },
  {
    path: "app/repo.py",
    content: `from .db import session
from .models import Courier, Delivery


def list_deliveries():
    rows = session.query(Delivery).filter(Delivery.day == today()).all()
    out = []
    for d in rows:
        courier = session.query(Courier).get(d.courier_id)
        out.append({"id": d.id, "parcel": d.parcel_id, "courier": courier.name})
    return out


def waiting_parcels():
    return session.query(Parcel).filter(Parcel.status == "waiting").all()


def free_couriers():
    return session.query(Courier).filter(Courier.busy.is_(False)).all()
`,
  },
  {
    path: "tests/test_dispatch.py",
    content: `from app.dispatch import Point, distance


def test_distance_is_symmetric():
    a, b = Point(1, 2), Point(4, 6)
    assert distance(a, b) == distance(b, a)


def test_distance_on_grid():
    assert distance(Point(0, 0), Point(3, 4)) == 7
`,
  },
];

export type LabyrinthIssue = { id: number; title: string; body: string; label: "bug" | "performance"; files: string[] };

export const LABYRINTH_ISSUES: LabyrinthIssue[] = [
  {
    id: 12,
    title: "East-zone couriers get parcels from across town",
    body: "Since last week's refactor, dispatch picks couriers that are clearly further away. Only happens when latitude and longitude differ a lot.",
    label: "bug",
    files: ["app/dispatch.py"],
  },
  {
    id: 15,
    title: "Route cache serves another zone's route",
    body: "Two zones share street names (\"Agora\" → \"Harbour\"). After someone in zone A asks for a route, zone B gets zone A's route for ten minutes.",
    label: "bug",
    files: ["app/cache.py"],
  },
  {
    id: 18,
    title: "GET /deliveries takes 4 s with 500 rows",
    body: "The endpoint gets slower the more deliveries there are in a day. DB monitoring shows hundreds of tiny queries per request.",
    label: "performance",
    files: ["app/repo.py", "app/dispatch.py"],
  },
];

const ARIADNE_REPLIES: { match: RegExp; reply: string }[] = [
  {
    match: /distance|east|zone.*far|nearest|issue\s*#?12/i,
    reply:
      "Follow the thread into `dispatch.distance`. A Manhattan distance has two terms — read each one aloud and check that every coordinate is paired with its twin. The two tests in `tests/test_dispatch.py` are a good way to prove it.",
  },
  {
    match: /cache|stale|route|issue\s*#?15/i,
    reply:
      "Ask what the cache key in `cache.route_between` is made of — and what the function takes as input. If two different inputs can produce the same key, they'll share an answer. While you're there, confirm the TTL comparison expires entries when it should.",
  },
  {
    match: /slow|perf|fast|n\+1|query|queries|deliveries|issue\s*#?18/i,
    reply:
      "Count the database round-trips in `repo.list_deliveries` for 500 rows. Is anything inside that loop asking the database again? Joining or eager-loading the courier usually turns N+1 queries into one. Also look at `dispatch.assign`: `taken` is a list — what does `in` cost on a list as it grows?",
  },
  {
    match: /explain|overview|architecture|how does|what does|start/i,
    reply:
      "Start at `app/routes.py`: three endpoints, each a thin wrapper. `/dispatch` reads parcels and couriers from `repo.py` and hands them to `dispatch.assign`. `/route/...` goes through the in-memory cache in `cache.py`. That's the whole map — three rooms, three issues.",
  },
  {
    match: /test|verify|prove/i,
    reply:
      "Write the smallest test that fails today. For the distance, a point that differs only in longitude is enough. For the cache, call it with the same streets in two zones and compare.",
  },
  {
    match: /answer|solution|fix it|write the code|give me/i,
    reply:
      "I'm the thread, not the hero — I can point the way, but the fix should be yours. Tell me which issue you're on and what you've ruled out, and I'll narrow the path.",
  },
];

export function ariadneReply(message: string): string {
  return (
    ARIADNE_REPLIES.find((r) => r.match.test(message))?.reply ??
    "Good question. Tell me which file you're in and what you expected to happen — then we'll compare it with what the code actually does. Most bugs here hide in a single line."
  );
}

export const ARIADNE_SUGGESTIONS = [
  "Give me an overview of the repo",
  "Where could the N+1 queries hide?",
  "Why might the cache return the wrong route?",
  "How do I prove the distance bug with a test?",
];

// ---------------------------------------------------------------------------------------
// The Oracle (voice interview). Plan per docs/INTERVIEWER.md: warm-up, portfolio,
// submission walkthrough, candidate's questions. At most 8 questions.
// ---------------------------------------------------------------------------------------

export function oracleQuestions(j: Journey): { block: string; text: string }[] {
  const name = firstName(j.candidate);
  const stack = j.candidate?.stack.length ? j.candidate.stack.slice(0, 2).join(" and ") : "FastAPI and PostgreSQL";
  return [
    { block: "Warm-up", text: `Welcome, ${name}. In a sentence or two, what kind of engineering work energises you most?` },
    { block: "Portfolio", text: `Your work leans on ${stack}. Walk me through one design decision in that stack you'd defend in a code review.` },
    { block: "Portfolio", text: "Tell me about a bug in your own project that took longest to find. How did you finally corner it?" },
    { block: "Submission", text: "In the Broken Ledger you repaired the pagination offset. How would you test page boundaries so it never regresses?" },
    { block: "Submission", text: "Explain the complexity of your Calm Streak solution, and when it might stop being fast enough." },
    { block: "Labyrinth", text: "In hermes-courier, which issue would you ship first to production, and why that one?" },
    { block: "Role", text: "When performance and readability pull in different directions, how do you decide?" },
    { block: "Your questions", text: "Finally — what would you like to ask about the role or the team?" },
  ];
}

export const ORACLE_SECONDS = 10 * 60;

// ---------------------------------------------------------------------------------------
// Verdict: BLUEPRINT §5 formulas, applied to the round results (deterministic).
// ---------------------------------------------------------------------------------------

export type Band = "strong" | "pass" | "borderline" | "not_yet";
export const BAND_LABEL: Record<Band, string> = { strong: "Strong", pass: "Pass", borderline: "Borderline", not_yet: "Not yet" };

export function bandOf(score: number): Band {
  if (score >= 80) return "strong";
  if (score >= 60) return "pass";
  if (score >= 45) return "borderline";
  return "not_yet";
}

export function correctnessOf(t: TaskOutcome): number {
  const rate = ([p, n]: [number, number]) => (n === 0 ? 0 : p / n);
  return 100 * (0.3 * rate(t.visible) + 0.7 * rate(t.hidden));
}

/** Sample round results so the report can be previewed without sitting every round. */
export function demoResults(j: Journey): Pick<Journey, "trials" | "labyrinth" | "oracle"> {
  const now = new Date().toISOString();
  return {
    trials: j.trials ?? {
      tasks: [
        { id: "domain", title: "The Broken Ledger", kind: "domain", visible: [3, 3], hidden: [8, 8], runs: 3, seconds: 1260 },
        { id: "dsa", title: "The Calm Streak", kind: "dsa", visible: [5, 5], hidden: [28, 30], runs: 4, seconds: 1580 },
      ],
      hintLevels: [1],
      quiz: { correct: 4, total: QUIZ.length },
      completedAt: now,
    },
    labyrinth: j.labyrinth ?? { issuesResolved: 2, issuesTotal: 3, findings: 4, perfIdeas: 2, filesTouched: 3, questionsAsked: 3, completedAt: now },
    oracle: j.oracle ?? {
      answered: 7,
      total: 8,
      seconds: 552,
      transcript: oracleQuestions(j)
        .slice(0, 3)
        .map((q, i) => ({
          q: q.text,
          a: [
            "Backend work where correctness matters — APIs other people build on.",
            "I chose dependency-injected auth in FastAPI so every route gets the same check and tests can swap it out.",
            "A timezone bug in monthly reports; I reproduced it with a fixed clock in tests and found the boundary was UTC, not local.",
          ][i],
        })),
      completedAt: now,
    },
  };
}

export function verdictOf(j: Journey) {
  const tasks = j.trials?.tasks ?? [];
  const correctness = tasks.map(correctnessOf);
  const mean = correctness.length ? correctness.reduce((a, b) => a + b, 0) / correctness.length : 0;
  const levels = j.trials?.hintLevels ?? [];
  let efficiency: number;
  if (levels.length === 0) {
    efficiency = mean / 100;
  } else {
    const ind = 1 - Math.min(1, levels.reduce((a, b) => a + b, 0) / 12);
    // PPH, TD and FREQ come from the event log in a live session; the demo credits them fully.
    efficiency = Math.max(0, Math.min(1, 0.35 + 0.2 + 0.15 + 0.3 * ind)) * Math.min(1, mean / 50);
  }
  const tier = (j.profile ?? DEMO_PROFILE).suggested_tier;
  const final = tier === "novice" ? mean : 0.8 * mean + 20 * efficiency;
  const rounded = Math.round(final * 10) / 10;
  return { tier, correctness, mean, efficiency, final: rounded, band: bandOf(rounded) };
}
