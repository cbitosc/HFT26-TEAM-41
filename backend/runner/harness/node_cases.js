"use strict";
/*
 * DSA harness for node20, copied read-only into the sandbox. Mirrors python_cases.py.
 *
 * Usage: node node_cases.js <inputs.json> <report.json> <module.js> <function> <timeout s> <params>
 *
 * <inputs.json> is a list of {"id", "input"}: inputs only, never expected answers. JS has
 * no keyword arguments, so an object input is passed positionally in the order of <params>
 * (comma-separated names); an array is spread; anything else is a single argument. The
 * candidate exports the function with module.exports (`{ name }` or the function itself).
 * The report is {"cases": [{"id", "output" | "error", "duration_ms"}]}, or {"fatal": "..."}
 * when the function can't be loaded. The backend compares outputs outside the sandbox.
 *
 * The module and every call run in a vm context with a timeout, so a synchronous infinite
 * loop is interrupted per case.
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { createRequire } = require("module");

const ERROR_CHARS = 500;

// Runs inside the context: the call and JSON conversion happen in the candidate's realm.
const CALL = `
globalThis.__call = function (fn, inputJson, params) {
  const input = JSON.parse(inputJson);
  let output;
  if (Array.isArray(input)) output = fn(...input);
  else if (input !== null && typeof input === "object") output = fn(...params.map((p) => input[p]));
  else output = fn(input);
  if (output === undefined) output = null;
  return JSON.stringify(output, (key, value) => {
    if (typeof value === "number" && !Number.isFinite(value)) {
      throw new TypeError("the output must be plain JSON (got " + value + ")");
    }
    return value;
  });
};
`;

function write(reportPath, report) {
  fs.writeFileSync(reportPath, JSON.stringify(report), "utf8");
}

function describe(err) {
  if (err && typeof err === "object" && "message" in err) {
    return `${err.name || "Error"}: ${err.message}`.slice(0, ERROR_CHARS);
  }
  return `thrown: ${String(err)}`.slice(0, ERROR_CHARS);
}

function isTimeout(err) {
  return Boolean(err && err.code === "ERR_SCRIPT_EXECUTION_TIMEOUT");
}

function load(context, modulePath, functionName, timeoutMs) {
  const filename = path.resolve(modulePath);
  const source = fs.readFileSync(filename, "utf8");
  const wrapper = vm.runInContext(
    `(function (exports, require, module, __filename, __dirname) {${source}\n})`,
    context,
    { filename },
  );
  const module = { exports: {} };
  context.__load = () =>
    wrapper.call(module.exports, module.exports, createRequire(filename), module, filename,
      path.dirname(filename));
  vm.runInContext("__load()", context, { timeout: timeoutMs });
  const exported = module.exports;
  const fn = typeof exported === "function" ? exported : exported && exported[functionName];
  if (typeof fn !== "function") {
    throw new TypeError(`${functionName} is not exported (use module.exports = { ${functionName} })`);
  }
  return fn;
}

function main() {
  const [inputsPath, reportPath, modulePath, functionName, timeout, params] = process.argv.slice(2);
  const cases = JSON.parse(fs.readFileSync(inputsPath, "utf8"));
  const paramNames = params ? params.split(",") : [];
  const timeoutMs = Math.round(Number(timeout) * 1000);
  const context = vm.createContext({ console });
  vm.runInContext(CALL, context);

  let fn;
  try {
    fn = load(context, modulePath, functionName, timeoutMs);
  } catch (err) {
    const why = isTimeout(err) ? `timed out after ${timeout} s` : describe(err);
    write(reportPath, { fatal: `could not load ${functionName} from ${modulePath}: ${why}`.slice(0, ERROR_CHARS) });
    process.exit(0);
  }

  context.__fn = fn;
  context.__params = paramNames;
  const results = [];
  for (const c of cases) {
    const entry = { id: c.id };
    const started = process.hrtime.bigint();
    try {
      context.__input = JSON.stringify(c.input);
      const out = vm.runInContext("__call(__fn, __input, __params)", context, { timeout: timeoutMs });
      entry.output = JSON.parse(out);
    } catch (err) {
      entry.error = isTimeout(err) ? `timed out after ${timeout} s` : describe(err);
    }
    entry.duration_ms = Math.round(Number(process.hrtime.bigint() - started) / 1e6);
    results.push(entry);
  }
  write(reportPath, { cases: results });
  // Timers or open handles left by candidate code must not keep the sandbox alive.
  process.exit(0);
}

main();
