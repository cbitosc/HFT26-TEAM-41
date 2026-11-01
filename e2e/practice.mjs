// Practice mode in headless Chromium against the running stack: pick a problem from the
// list, run the starter (fails), paste a solution into the bundled Monaco, Run, try a
// custom input, Submit (Accepted), then switch to JavaScript. Nothing may leave the stack.
// Usage: node practice.mjs   (BASE_URL defaults to http://localhost:3000)
import assert from "node:assert/strict";
import { mkdirSync } from "node:fs";
import { chromium } from "playwright";

const BASE_URL = process.env.BASE_URL ?? "http://localhost:3000";
const ARTIFACTS = new URL("./artifacts/", import.meta.url).pathname;
const PAGE_TIMEOUT_MS = 180_000;
const JOB_TIMEOUT_MS = 120_000;

const PY_SOLUTION = `def two_sum(nums: list[int], target: int) -> list[int]:
    seen = {}
    for i, n in enumerate(nums):
        if target - n in seen:
            return [seen[target - n], i]
        seen[n] = i
    return []
`;
const JS_SOLUTION = `function two_sum(nums, target) {
  const seen = new Map();
  for (let i = 0; i < nums.length; i++) {
    if (seen.has(target - nums[i])) return [seen.get(target - nums[i]), i];
    seen.set(nums[i], i);
  }
  return [];
}

module.exports = { two_sum };
`;

const started = Date.now();
const step = (message) => console.log(`[practice ${((Date.now() - started) / 1000).toFixed(1)}s] ${message}`);

function isLocal(url) {
  const { protocol, hostname } = new URL(url);
  return !protocol.startsWith("http") || hostname === "localhost" || hostname === "127.0.0.1";
}

async function main(page, external) {
  await page.goto(`${BASE_URL}/practice`, { timeout: PAGE_TIMEOUT_MS });
  await page.getByRole("link", { name: /Two sum/ }).waitFor({ timeout: PAGE_TIMEOUT_MS });
  step("problem list loaded");
  await page.getByLabel("Search by title").fill("two sum");
  assert.equal(await page.getByRole("link", { name: /Two sum/ }).count(), 1);
  await page.getByRole("link", { name: /Two sum/ }).click();
  await page.locator(".monaco-editor").waitFor({ timeout: PAGE_TIMEOUT_MS });
  await page.getByRole("heading", { name: "Two sum" }).waitFor();
  step("problem page loaded with the bundled Monaco editor");

  const runButton = page.getByRole("button", { name: /^(Run|Running…)$/ });
  const submitButton = page.getByRole("button", { name: /^(Submit|Submitting…)$/ });
  async function idle() {
    await page.waitForFunction(
      () => [...document.querySelectorAll("header button")].every((b) => !/ing…$/.test(b.textContent)),
      null,
      { timeout: JOB_TIMEOUT_MS },
    );
  }
  async function paste(content) {
    await page.locator(".monaco-editor .view-lines").click();
    await page.evaluate((text) => navigator.clipboard.writeText(text), content);
    await page.keyboard.press("ControlOrMeta+A");
    await page.keyboard.press("ControlOrMeta+V");
  }

  await runButton.click();
  await page.getByText(/^0 \/ 5 examples passed$/).waitFor({ timeout: JOB_TIMEOUT_MS });
  await idle();
  step("starter fails the examples");

  await paste(PY_SOLUTION);
  await runButton.click();
  await page.getByText("All examples passed").waitFor({ timeout: JOB_TIMEOUT_MS });
  await idle();
  step("Python solution passes the examples");

  await page.getByRole("tab", { name: "Custom input" }).click();
  await page.locator("#custom-input").fill('{"nums": [2, 7, 11, 15], "target": 9}');
  await runButton.click();
  await page.getByText("[0, 1]", { exact: true }).waitFor({ timeout: JOB_TIMEOUT_MS });
  await idle();
  step("custom input returns [0, 1]");

  await submitButton.click();
  await page.getByText("Accepted").waitFor({ timeout: JOB_TIMEOUT_MS });
  assert.ok(await page.getByText(/^35 \/ 35 cases passed/).isVisible());
  await idle();
  step("Submit: Accepted, 35 / 35");

  // Reload: the code was saved in this browser.
  await page.reload();
  await page.locator(".monaco-editor").waitFor({ timeout: PAGE_TIMEOUT_MS });
  await submitButton.click();
  await page.getByText("Accepted").waitFor({ timeout: JOB_TIMEOUT_MS });
  await idle();
  step("code survived a reload");

  await page.getByLabel("Language").selectOption("javascript");
  await page.waitForFunction(() => document.body.innerText.includes("module.exports"));
  await paste(JS_SOLUTION);
  await submitButton.click();
  await page.getByText("Accepted").waitFor({ timeout: JOB_TIMEOUT_MS });
  await idle();
  step("JavaScript solution: Accepted");

  assert.deepEqual(external, [], "requests left the stack");
}

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin: BASE_URL });
const page = await context.newPage();
const external = [];
const pageErrors = [];
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
  console.error(`[practice] FAIL: ${err.message}`);
  if (pageErrors.length) console.error(`[practice] page errors:\n  ${pageErrors.join("\n  ")}`);
  if (external.length) console.error(`[practice] blocked external requests:\n  ${external.join("\n  ")}`);
  mkdirSync(ARTIFACTS, { recursive: true });
  await page.screenshot({ path: `${ARTIFACTS}practice-failure.png`, fullPage: true }).catch(() => {});
  console.error(`[practice] screenshot: e2e/artifacts/practice-failure.png (page ${page.url()})`);
} finally {
  await browser.close();
}
process.exit(failed ? 1 : 0);
