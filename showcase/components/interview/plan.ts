import { AGENT } from "@/lib/site";

// Question plans and the adaptive turn logic for the browser-only practice interview.
// The structure (sections, planned questions with follow-ups, a word-count difficulty
// signal, hard time and turn ceilings) follows DeepInterview's live loop
// (apps/agent/src/deepinterview_agent/live/state.py and guard.py, Apache-2.0).
// Everything here is plain code: no model call, no randomness, so the same answers
// always get the same next question.

export type Section = "intro" | "project" | "technical" | "assessment" | "wrap";

export type Question = {
  id: string;
  section: Section;
  /** May contain {project} and {stack}. */
  text: string;
  /** 1–5, as in DeepInterview's plan. */
  difficulty: number;
  /** Asked once when the answer is rich (≥ RICH_WORDS). */
  deeper?: string;
  /** Asked once when the answer is thin (< THIN_WORDS). */
  simpler?: string;
  competency: string;
};

export type Track = { id: string; label: string; note: string; questions: Question[] };

export type Setup = { name: string; project: string; stack: string; track: string };

// DeepInterview uses 12 and 80 words. Spoken demo answers run shorter, so the "rich"
// bar is lower here; the thin bar is the same.
export const THIN_WORDS = 12;
export const RICH_WORDS = 45;

/** Hard ceilings, like DeepInterview's SessionGuard. */
export const MAX_SECONDS = 12 * 60;
export const MAX_TURNS = 40;

export const SECTION_LABEL: Record<Section, string> = {
  intro: "Intro",
  project: "Your project",
  technical: "Technical",
  assessment: "The assessment",
  wrap: "Wrap-up",
};

const INTRO: Question[] = [
  {
    id: "intro-1",
    section: "intro",
    text: "To start, tell me about {project}: what it does, and which part you built yourself.",
    difficulty: 1,
    simpler: "No problem. In one or two sentences, what does {project} do for its users?",
    deeper: "You mentioned a lot there. Which of those parts was the hardest to get right, and why?",
    competency: "Communication",
  },
];

const WRAP: Question[] = [
  {
    id: "wrap-1",
    section: "wrap",
    text: "Last one. If you had another week on {project}, what would you change first?",
    difficulty: 2,
    simpler: "Even one small thing is fine. What would you fix or clean up first?",
    competency: "Reflection",
  },
];

const TRACKS: Track[] = [
  {
    id: "backend",
    label: "Backend",
    note: "APIs, data, testing, performance",
    questions: [
      {
        id: "be-1",
        section: "project",
        text: "Walk me through how a single request moves through {project}, from the route to the database and back.",
        difficulty: 2,
        simpler: "Pick one endpoint you know well. What happens when it gets called?",
        deeper: "Where in that path would you put a cache, and how would you keep it from serving stale data?",
        competency: "System understanding",
      },
      {
        id: "be-2",
        section: "technical",
        text: "Two requests try to update the same row at the same time. How does your {stack} code keep the data correct?",
        difficulty: 3,
        simpler: "Think of two people editing the same record. What could go wrong, and how would you notice?",
        deeper: "Would you choose row locks or optimistic versioning here? What does each cost you?",
        competency: "Data integrity",
      },
      {
        id: "be-3",
        section: "technical",
        text: "A list endpoint is slow once the table reaches a million rows. How do you find out why, and what do you try first?",
        difficulty: 3,
        simpler: "What tool or log would you open first to see where the time goes?",
        deeper: "Offset pagination is part of the problem. What would you replace it with, and what breaks for clients?",
        competency: "Performance",
      },
      {
        id: "be-4",
        section: "assessment",
        text: "In the assessment, page two of a list returned the wrong rows. How would you track a bug like that down?",
        difficulty: 2,
        simpler: "What is the first test you would write to show the bug?",
        deeper: "How would you make sure that bug can never come back, beyond the one test?",
        competency: "Debugging",
      },
    ],
  },
  {
    id: "frontend",
    label: "Frontend",
    note: "State, rendering, accessibility",
    questions: [
      {
        id: "fe-1",
        section: "project",
        text: "How is state organised in {project}? What lives on the server, and what lives in the browser?",
        difficulty: 2,
        simpler: "Pick one screen. Where does its data come from when it loads?",
        deeper: "When two components need the same data, how do you keep them in sync without prop drilling everywhere?",
        competency: "System understanding",
      },
      {
        id: "fe-2",
        section: "technical",
        text: "A page built with {stack} feels slow when you type into a search box. How do you find the cause?",
        difficulty: 3,
        simpler: "What would you check first: the network, or rendering?",
        deeper: "Say it's re-rendering a long list on every key press. What are your options, and which would you pick?",
        competency: "Performance",
      },
      {
        id: "fe-3",
        section: "technical",
        text: "How do you make sure a custom dropdown works for someone using only a keyboard or a screen reader?",
        difficulty: 3,
        simpler: "Which keys should a dropdown respond to?",
        deeper: "What ARIA roles and states would you use, and when would you just use a native select instead?",
        competency: "Accessibility",
      },
      {
        id: "fe-4",
        section: "assessment",
        text: "In the assessment you ran visible tests before submitting. How do you decide what to test in UI code?",
        difficulty: 2,
        simpler: "Name one thing in a form that you would always test.",
        deeper: "Where do you draw the line between unit tests, component tests and end-to-end tests?",
        competency: "Testing",
      },
    ],
  },
  {
    id: "general",
    label: "Generalist",
    note: "Trade-offs, debugging, algorithms",
    questions: [
      {
        id: "ge-1",
        section: "project",
        text: "Tell me about a technical decision in {project} that you would make differently today.",
        difficulty: 2,
        simpler: "Even a library choice counts. What would you swap out?",
        deeper: "What did that decision cost you over time, and when did you notice?",
        competency: "Judgement",
      },
      {
        id: "ge-2",
        section: "technical",
        text: "Describe the hardest bug you've fixed. How did you narrow it down?",
        difficulty: 3,
        simpler: "What was the first clue that something was wrong?",
        deeper: "Looking back, what would have caught it before it reached anyone?",
        competency: "Debugging",
      },
      {
        id: "ge-3",
        section: "assessment",
        text: "You solved an algorithms task in the assessment. Explain how you would find the k most frequent words in a large file, and its cost.",
        difficulty: 3,
        simpler: "Start simple: how would you count how often each word appears?",
        deeper: "Now the file doesn't fit in memory. What changes?",
        competency: "Algorithms",
      },
      {
        id: "ge-4",
        section: "technical",
        text: "How do you review someone else's pull request? What do you look for first?",
        difficulty: 2,
        simpler: "What is one thing that would make you ask for changes?",
        deeper: "How do you push back on a design you disagree with without stalling the work?",
        competency: "Collaboration",
      },
    ],
  },
];

export const TRACK_LIST = TRACKS.map(({ id, label, note }) => ({ id, label, note }));

export const DEMO_SETUP: Setup = {
  name: "",
  project: "the expenses API",
  stack: "FastAPI and Postgres",
  track: "backend",
};

export function planFor(setup: Setup): Question[] {
  const track = TRACKS.find((t) => t.id === setup.track) ?? TRACKS[0];
  return [...INTRO, ...track.questions, ...WRAP];
}

export function fill(text: string, setup: Setup): string {
  return text
    .replaceAll("{project}", setup.project.trim() || "your project")
    .replaceAll("{stack}", setup.stack.trim() || "your");
}

export function words(text: string): number {
  return text.trim().split(/\s+/).filter(Boolean).length;
}

export type Move = "simpler" | "deeper" | "advance";

/**
 * What to ask next for the current question, given the answer just heard.
 * Same idea as DeepInterview's evaluate_difficulty: thin answers get an easier
 * follow-up, rich ones a harder one, and each follow-up is asked at most once.
 */
export function nextMove(q: Question, answerWords: number, followupAsked: boolean): Move {
  if (followupAsked) return "advance";
  if (answerWords < THIN_WORDS && q.simpler) return "simpler";
  if (answerWords >= RICH_WORDS && q.deeper) return "deeper";
  return "advance";
}

// Short acknowledgements before the next question, rotated by turn number.
const ACKS = ["Thanks.", "Okay, got it.", "Makes sense.", "Good, thank you.", "Alright."];

export function ack(turn: number): string {
  return ACKS[turn % ACKS.length];
}

export function greeting(setup: Setup): string {
  const who = setup.name.trim() ? `Hi ${setup.name.trim()}, ` : "Hi, ";
  return `${who}I'm ${AGENT}, an AI interviewer. Thanks for joining. This is a short practice interview, about ten minutes. Take your time, and say "next" whenever you want to move on.`;
}

export const CLOSING =
  "That's all my questions. Thank you, that was a good conversation. Your notes are ready below.";

export const TIME_UP = "We're at time, so let's wrap up here. Thank you, your notes are ready below.";

const FILLERS = ["um", "uh", "erm", "like", "basically", "actually", "you know", "sort of", "kind of", "i mean"];

export function fillerCount(text: string): number {
  const t = ` ${text.toLowerCase().replace(/[^a-z' ]+/g, " ")} `;
  let n = 0;
  for (const f of FILLERS) n += t.split(` ${f} `).length - 1;
  return n;
}
