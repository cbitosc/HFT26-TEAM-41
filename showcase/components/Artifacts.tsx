import { FACTS } from "@/lib/site";

// One small piece of evidence per pipeline stage. Real repo data unless marked.

function Portfolio() {
  return (
    <pre className="code">
      {`{
  "basics": { "label": "Backend Developer (Python)" },
  "skills": [{ "name": "Backend",
               "keywords": ["Python", "FastAPI", "SQLAlchemy"] }],
  "projects": [ `}<span className="c">{`/* 3 projects */`}</span>{` ],
  "assessment": {
    "dsaTopicsSolved": { "arrays": 48, "hashing": 35,
                         "two_pointers": 22, "dp": 11 }
  }
}`}
    </pre>
  );
}

function Profile() {
  return (
    <div className="art-card">
      <dl className="kv">
        <dt>domain</dt><dd>backend</dd>
        <dt>runtime</dt><dd>python311</dd>
        <dt>concepts</dt><dd>caching, reporting, validation</dd>
        <dt>novice topics</dt><dd>arrays, hashing, two_pointers, trees, sliding_window, dp</dd>
        <dt>suggested tier</dt><dd>master</dd>
        <dt>sources</dt><dd>rules, rules, rules</dd>
      </dl>
      <p className="small">
        {FACTS.taxonomyTopics} topics in the taxonomy. A topic is only allowed if the candidate claimed it, at a count
        that clears the tier&apos;s threshold (1 easy, 5 medium, 15 hard).
      </p>
    </div>
  );
}

function Tasks() {
  return (
    <div>
      <pre className="code">
        <span className="c">{`# app/utils.py · paginate · operator off_by_one`}</span>
        {`
count_stmt = select(func.count()).select_from(...)
total = session.scalar(count_stmt) or 0
`}
        <span className="del">{`-offset = (page - 1) * page_size`}</span>
        <span className="add">{`+offset = page * page_size`}</span>
        {`items = list(session.scalars(stmt.limit(page_size).offset(offset)))`}
      </pre>
      <p className="small art-note">
        <code>make mutate</code> on pagination: {FACTS.mutationCandidates} candidate bugs, {FACTS.mutationChecked}{" "}
        run in the sandbox, {FACTS.mutationKept} kept (each breaks 1–40% of the suite, including a pagination test).
      </p>
    </div>
  );
}

const CHECKS: [string, "done" | "optional" | "planned"][] = [
  ["Reference passes every test, 3 times in a row", "done"],
  ["Starter fails at least one concept test", "done"],
  ["Unrelated concepts' tests still pass", "done"],
  ["Edits stay inside the scoped files", "done"],
  ["No reference code leaks into the starter", "done"],
  ["Mutation score of the test suite (mutmut)", "optional"],
  ["AI solve-rate probe: 3 attempts", "planned"],
];

function Gate() {
  return (
    <div className="art-card">
      <ul className="checks">
        {CHECKS.map(([text, s]) => (
          <li key={text} data-done={s === "done"}>
            <span aria-hidden>{s === "done" ? "✓" : "○"}</span>
            {text}
            {s !== "done" && <em>{s === "optional" ? "optional" : "planned, P2.8"}</em>}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Ide() {
  return (
    <pre className="code term">
      <span className="c">{`$ Run   (fresh container, network off)`}</span>
      {`
visible  tests/test_pagination.py   `}<span className="n">{`2 / 3 passed`}</span>{`
hidden   run in a separate sandbox  logged, not shown

`}<span className="c">{`# fix line 35, Run again`}</span>{`
visible  tests/test_pagination.py   `}<span className="s">{`3 / 3 passed`}</span>{`
dsa      longest_unique_substring   `}<span className="s">{`5 / 5 passed`}</span>{`
`}<span className="c">{`# median Run → visible result: ${FACTS.visibleResultS} s`}</span>
    </pre>
  );
}

function Assistant() {
  return (
    <div className="art-card">
      <ol className="ladder">
        <li><b>L1</b> Points at the area: which function, which behaviour.</li>
        <li><b>L2</b> Names the idea: &ldquo;a 1-based page starts at index 0&rdquo;.</li>
        <li><b>L3</b> A partial step, capped in size, never the reference.</li>
      </ol>
      <p className="small">Every hint is logged. Fewer and better-timed hints score higher on AI efficiency.</p>
    </div>
  );
}

function Report() {
  return (
    <div className="art-card report-mini">
      <div className="report-score">
        <span className="display">100</span>
        <span>Strong</span>
      </div>
      <dl className="kv">
        <dt>domain</dt><dd>hidden {FACTS.hiddenDomain} / {FACTS.hiddenDomain}, 2 runs</dd>
        <dt>dsa</dt><dd>hidden {FACTS.hiddenDsa} / {FACTS.hiddenDsa}, 1 run</dd>
        <dt>re-grade</dt><dd>identical</dd>
      </dl>
      <p className="small">The demo session, as asserted by <code>make e2e</code>.</p>
    </div>
  );
}

export const ARTIFACTS: Record<string, () => React.JSX.Element> = {
  portfolio: Portfolio,
  profile: Profile,
  tasks: Tasks,
  gate: Gate,
  ide: Ide,
  assistant: Assistant,
  report: Report,
};
