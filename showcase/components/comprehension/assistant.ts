import { FILE_NOTES } from "./task";

// Stand-in for code-compr's /api/chat (an OpenAI-compatible model with the snapshot
// in its system prompt). A static page can't call a model, so replies are canned and
// picked by keyword. They are written to behave like a helpful model would: a lazy
// "fix the bug" gets a ready patch, which is exactly what the AI-fluency rubric
// checks for when it looks for a verbatim paste.

const PATCH = "```python\n    pages = (len(items) + per_page - 1) // per_page\n    page = max(1, min(page, pages))\n```";

const RULES: { test: RegExp; reply: string }[] = [
  {
    test: /\b(fix (the|this|it)|solve|give me|just (do|write)|the answer|write the (fix|code))\b/i,
    reply: `The page count uses floor division, so a partial last page is dropped. Round up instead:\n\n${PATCH}\n\nI haven't run this. Check it with 7 items at per_page=3 (expect 3 pages, last page [6]) and 2 items at per_page=10 (expect 1 page) before you keep it.`,
  },
  {
    test: /\b(slow|cost|efficien|cheap|perf|fast|quadratic|memory|alloc|copy|copies)/i,
    reply: "Look at pagekit/links.py. page_links calls paginate once per page, and each call copies the whole input with list(items). That's a full copy of n items for every one of n / per_page pages, so roughly quadratic in the list size. Computing the page count once (ceil of len / per_page) and building the links in a plain loop needs no copies and no paginate calls.",
  },
  {
    test: /\b(test|verify|check|edge|case|reproduce|wrong|sure|fail)/i,
    reply: "Try a count that isn't a multiple of per_page: paginate(list(range(7)), page=3, per_page=3). Today it returns page 2 with [3, 4, 5] and pages=2. A correct fix gives page 3 with [6] and pages=3. Also try 2 items at per_page=10, which should give pages=1. The existing tests only use 6 items, so they all pass either way.",
  },
  {
    test: /(\/\/|floor|divi|round|ceil|pages\b)/i,
    reply: "len(items) // per_page is floor division: 7 // 3 is 2, so the seventh item has no page. You want the ceiling. In Python that's math.ceil(len(items) / per_page), or (len(items) + per_page - 1) // per_page to stay in integers.",
  },
];

export function scriptedReply(message: string): string {
  const lower = message.toLowerCase();
  const named = Object.keys(FILE_NOTES).find((path) => {
    const base = path.split("/").pop() ?? path;
    return lower.includes(path.toLowerCase()) || lower.includes(base.toLowerCase().replace(/\.\w+$/, ""));
  });
  const rule = RULES.find((item) => item.test.test(message));
  // A specific question about a file gets the file note first, then any matching hint.
  if (named && rule && !/fix (the|this|it)|solve/i.test(message)) return `${FILE_NOTES[named]}\n\n${rule.reply}`;
  if (rule) return rule.reply;
  if (named) return FILE_NOTES[named];
  return "I can only see this snapshot. Name a file or a function and say what you expected to happen, and I can be specific. The issue is about pagekit/paginate.py.";
}
