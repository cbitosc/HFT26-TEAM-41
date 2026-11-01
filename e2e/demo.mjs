// `make e2e`: the demo flow in headless Chromium against the running stack.
// Opens a fresh seed-demo session, runs the starter (a visible test must fail), fixes
// both tasks by pasting into the bundled Monaco editor, runs them, submits, opens the
// report and checks the scores against the API. Every request that would leave the
// stack (e.g. a Monaco CDN) is blocked and fails the run.
// Usage: node demo.mjs <session-id>   (BASE_URL defaults to http://localhost:3000)
import assert from "node:assert/strict";
import { mkdirSync } from "node:fs";
import { chromium } from "playwright";

const BASE_URL = process.env.BASE_URL ?? "http://localhost:3000";
const ARTIFACTS = new URL("./artifacts/", import.meta.url).pathname;
const PAGE_TIMEOUT_MS = 180_000; // first `next dev` compile of a page and the Monaco chunk
const RUN_TIMEOUT_MS = 120_000; // visible + hidden sandbox runs
const GRADE_TIMEOUT_MS = 180_000; // submit grades every task in fresh sandboxes
const FOCUS_DWELL_MS = 2500; // "read the code" before editing: at least two focus samples
const EDIT_SAMPLE_MS = 1200; // let the per-second edit sample fire before leaving the editor

// The candidate's fixes. The domain fix is a one-line edit of the starter; the DSA
// solution is written from scratch (not the backend's reference).
const DOMAIN_BUG = "offset = (page - 2) * page_size";
const DOMAIN_FIX = "offset = (page - 1) * page_size";
const DSA_SOLUTION = `def length_of_longest_substring(s: str) -> int:
    window = set()
    left = best = 0
    for char in s:
        while char in window:
            window.remove(s[left])
            left += 1
        window.add(char)
        best = max(best, len(window))
    return best
`;

// What the report must show after both fixes.
const EXPECTED = {
  final_score: 100,
  band: "strong",
  bandLabel: "Strong",
  correctness: 100,
  runs: { domain: 2, dsa: 1 }, // domain: starter + fix
};

const sessionId = process.argv[2];
if (!sessionId) {
  console.error("usage: node demo.mjs <session-id>");
  process.exit(2);
}

const started = Date.now();
const step = (message) => console.log(`[e2e ${((Date.now() - started) / 1000).toFixed(1)}s] ${message}`);

async function api(path, init) {
  const res = await fetch(`${BASE_URL}/api${path}`, { cache: "no-store", ...init });
  if (!res.ok) assert.fail(`${init?.method ?? "GET"} ${path} returned ${res.status}: ${await res.text()}`);
  return res.json();
}

function isLocal(url) {
  const { protocol, hostname } = new URL(url);
  return !protocol.startsWith("http") || hostname === "localhost" || hostname === "127.0.0.1";
}

/** The domain task's one-line fix, found in the starter the browser sees. */
function domainFix(task) {
  const hits = Object.entries(task.starter_files).filter(([, content]) => content.includes(DOMAIN_BUG));
  assert.equal(hits.length, 1, `expected the bug "${DOMAIN_BUG}" in exactly one starter file`);
  const [path, buggy] = hits[0];
  assert.equal(buggy.split(DOMAIN_BUG).length, 2, `"${DOMAIN_BUG}" occurs more than once in ${path}`);
  return { path, content: buggy.replace(DOMAIN_BUG, DOMAIN_FIX) };
}

async function main(page, external) {
  const session = await api(`/sessions/${sessionId}`);
  assert.equal(session.status, "active", "the session must be fresh: run `make seed-demo` again");
  const refs = [...session.tasks].sort((a, b) => a.order - b.order);
  assert.deepEqual(
    refs.map((t) => t.kind),
    ["domain", "dsa"],
  );
  const [domain, dsa] = await Promise.all(refs.map((t) => api(`/sessions/${sessionId}/tasks/${t.task_id}`)));
  const fixes = {
    [domain.task_id]: domainFix(domain),
    [dsa.task_id]: { path: Object.keys(dsa.starter_files)[0], content: DSA_SOLUTION },
  };

  const runButton = page.getByRole("button", { name: /^(Run|Running…)$/ });
  const summary = page.getByText(/^\d+\/\d+ passed$/);

  async function openTask(index) {
    await page.getByRole("button", { name: `${index + 1}. ${index === 0 ? "Domain" : "DSA"} task` }).click();
  }

  async function run(label) {
    await runButton.click();
    await page.waitForFunction(
      () => {
        const button = [...document.querySelectorAll("header button")].find((b) => b.textContent === "Run");
        return button && !button.disabled; // the whole job (visible + hidden) has finished
      },
      null,
      { timeout: RUN_TIMEOUT_MS },
    );
    const text = await summary.textContent({ timeout: 1000 }).catch(() => null);
    assert.ok(text, `${label}: no test summary after the run`);
    const [passed, total] = text.replace(" passed", "").split("/").map(Number);
    step(`${label}: ${passed}/${total} visible tests passed`);
    return { passed, total };
  }

  // Replace a file's content in Monaco: select all, then paste with Ctrl+V. Typed text
  // would be auto-indented by the editor; a paste is inserted as is. The pauses keep the
  // editor focused across telemetry samples (once per second), so time on task is recorded.
  async function pasteInto(path, content) {
    await page.locator(`button[title="${path}"]`).click(); // file tree
    await page.locator(".monaco-editor .view-lines").click();
    await page.waitForTimeout(FOCUS_DWELL_MS);
    await page.evaluate((text) => navigator.clipboard.writeText(text), content);
    await page.keyboard.press("ControlOrMeta+A");
    await page.keyboard.press("ControlOrMeta+V");
    await page.waitForTimeout(EDIT_SAMPLE_MS);
  }

  async function assertSaved(taskId) {
    const saved = await api(`/sessions/${sessionId}/tasks/${taskId}/files`);
    const { path, content } = fixes[taskId];
    assert.equal(saved.files?.[path], content, `${taskId}: the saved ${path} is not what was typed`);
  }

  step(`open ${BASE_URL}/session/${sessionId}`);
  await page.goto(`${BASE_URL}/session/${sessionId}`, { timeout: PAGE_TIMEOUT_MS });
  await page.locator(".monaco-editor").waitFor({ timeout: PAGE_TIMEOUT_MS });
  step("IDE loaded with the bundled Monaco editor");

  // Domain task: the starter fails a visible test, the one-line fix passes them all.
  await openTask(0);
  const starter = await run("domain starter");
  assert.ok(starter.passed < starter.total, "the starter must fail at least one visible test");
  await pasteInto(fixes[domain.task_id].path, fixes[domain.task_id].content);
  const domainRun = await run("domain fixed");
  assert.equal(domainRun.passed, domainRun.total, "the fixed domain task must pass every visible test");
  await assertSaved(domain.task_id);

  // DSA task.
  await openTask(1);
  await pasteInto(fixes[dsa.task_id].path, fixes[dsa.task_id].content);
  const dsaRun = await run("dsa solved");
  assert.equal(dsaRun.passed, dsaRun.total, "the DSA solution must pass every visible case");
  await assertSaved(dsa.task_id);

  // Submit through the confirm dialog.
  await page.getByRole("button", { name: "Submit", exact: true }).click();
  await page.getByRole("button", { name: "Submit", exact: true }).last().click();
  await page.getByRole("heading", { name: "Submitted" }).waitFor({ timeout: 30_000 });
  step("submitted");

  // Report: wait for grading, then compare every shown number with the API breakdown.
  await page.goto(`${BASE_URL}/report/${sessionId}`, { timeout: PAGE_TIMEOUT_MS });
  await page.getByTestId("final-score").waitFor({ timeout: GRADE_TIMEOUT_MS });
  const score = await api(`/sessions/${sessionId}/score`);
  assert.equal(score.status, "graded");
  const b = score.breakdown;
  step(`graded: final ${b.final_score} (${b.band})`);

  assert.equal(b.final_score, EXPECTED.final_score, "final score");
  assert.equal(b.band, EXPECTED.band, "band");
  assert.deepEqual(
    b.tasks.map((t) => t.task_id),
    refs.map((t) => t.task_id),
  );
  for (const t of b.tasks) {
    assert.ok(t.hidden.total > 0, `${t.task_id}: no hidden tests`);
    assert.equal(t.visible.passed, t.visible.total, `${t.task_id}: visible tests`);
    assert.equal(t.hidden.passed, t.hidden.total, `${t.task_id}: hidden tests`);
    assert.equal(t.correctness, EXPECTED.correctness, `${t.task_id}: correctness`);
    assert.equal(t.runs, EXPECTED.runs[t.kind], `${t.task_id}: runs`);
    // Scoring v2: the gate-certified domain task counts only its fail_to_pass tests; DSA all cases.
    assert.equal(t.rates_over, t.kind === "domain" ? "fail_to_pass" : "all_tests", `${t.task_id}: rates_over`);
    assert.equal(t.regression_factor, 1, `${t.task_id}: regression factor`);
    assert.ok(t.time_ms !== null && t.time_ms > 0, `${t.task_id}: time on task not recorded`);
    step(
      `${t.task_id}: visible ${t.visible.passed}/${t.visible.total}, hidden ${t.hidden.passed}/${t.hidden.total}, ` +
        `correctness ${t.correctness}, ${t.runs} runs, ${(t.time_ms / 1000).toFixed(1)} s`,
    );
  }

  assert.equal(await page.getByTestId("final-score").textContent(), b.final_score.toFixed(2), "report: final score");
  assert.equal(await page.getByTestId("band").textContent(), EXPECTED.bandLabel, "report: band");
  for (const t of b.tasks) {
    const row = page.locator(`[data-testid="task-row"][data-task-id="${t.task_id}"]`);
    const cell = (field) => row.locator(`[data-field="${field}"]`).textContent();
    assert.ok((await cell("visible")).startsWith(`${t.visible.passed}/${t.visible.total}`), `report: ${t.task_id} visible`);
    if (t.visible_f2p) {
      const fixed = `fixed ${t.visible_f2p.passed}/${t.visible_f2p.total}`;
      assert.ok((await cell("visible")).includes(fixed), `report: ${t.task_id} visible fail_to_pass`);
    }
    assert.ok((await cell("hidden")).startsWith(`${t.hidden.passed}/${t.hidden.total}`), `report: ${t.task_id} hidden`);
    assert.ok((await cell("correctness")).startsWith(t.correctness.toFixed(2)), `report: ${t.task_id} correctness`);
    assert.equal(await cell("runs"), String(t.runs), `report: ${t.task_id} runs`);
    const mutation = t.mutation_score == null ? "not measured" : `${Math.round(t.mutation_score * 100)}%`;
    assert.equal(await cell("mutation"), mutation, `report: ${t.task_id} mutation score`);
  }
  step("report matches the breakdown JSON");

  // Re-grade from stored records gives the identical breakdown.
  await page.getByRole("button", { name: "Re-grade" }).click();
  await page.getByText("identical score").waitFor({ timeout: 30_000 });
  assert.deepEqual((await api(`/sessions/${sessionId}/score`)).breakdown, b, "re-grade changed the breakdown");
  step("re-grade: identical breakdown");

  assert.deepEqual(external, [], "requests left the stack");
}

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin: BASE_URL });
const page = await context.newPage();
const external = [];
const pageErrors = [];
// Nothing may leave the stack: this is what proves Monaco is bundled, not fetched.
await page.route(
  (url) => !isLocal(url.href),
  (route) => {
    external.push(route.request().url());
    return route.abort();
  },
);
page.on("pageerror", (err) => pageErrors.push(err.message));

let failed = false;
try {
  await main(page, external);
  assert.deepEqual(pageErrors, [], "uncaught errors in the page");
  step("PASS");
} catch (err) {
  failed = true;
  console.error(`[e2e] FAIL: ${err.message}`);
  if (pageErrors.length) console.error(`[e2e] page errors:\n  ${pageErrors.join("\n  ")}`);
  if (external.length) console.error(`[e2e] blocked external requests:\n  ${external.join("\n  ")}`);
  mkdirSync(ARTIFACTS, { recursive: true });
  await page.screenshot({ path: `${ARTIFACTS}failure.png`, fullPage: true }).catch(() => {});
  console.error(`[e2e] screenshot: e2e/artifacts/failure.png (page ${page.url()})`);
} finally {
  await browser.close();
}
process.exit(failed ? 1 : 0);
