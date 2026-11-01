// Which files a candidate may edit. Mirrors backend/app/workspace.py (the backend is
// authoritative: a save or run with any other path returns 422). Keep the two in sync.
import type { CandidateTaskView } from "./types";

const TEST_DIRS = new Set(["tests", "test", "__tests__"]);
const PROTECTED_NAMES = new Set([
  "conftest.py",
  "pytest.ini",
  "tox.ini",
  "setup.cfg",
  "pyproject.toml",
  "sitecustomize.py",
  "usercustomize.py",
  "package.json",
  ".npmrc",
  ".babelrc",
]);
const PROTECTED_PATTERNS = [/^.*\.pth$/, /^jest\.config\..*$/, /^\.babelrc\..*$/, /^babel\.config\..*$/];
const TEST_FILE_PATTERNS = [/^(test_.*|.*_test)\.py$/, /^.*\.(test|spec)\.(js|jsx|ts|tsx|mjs|cjs)$/];

export function protectedReason(path: string): string | null {
  const parts = path.toLowerCase().split("/");
  const name = parts[parts.length - 1];
  if (parts.slice(0, -1).some((p) => TEST_DIRS.has(p))) return "test directories are read-only";
  if (PROTECTED_NAMES.has(name) || PROTECTED_PATTERNS.some((p) => p.test(name))) {
    return `${name} is test or package configuration`;
  }
  if (TEST_FILE_PATTERNS.some((p) => p.test(name))) return "test files are read-only";
  return null;
}

export function isEditable(task: CandidateTaskView, path: string): boolean {
  return path in task.starter_files && protectedReason(path) === null;
}

/** Every file the candidate sees: starter files plus visible tests, sorted by path. */
export function allFiles(task: CandidateTaskView): Record<string, string> {
  const files: Record<string, string> = { ...task.starter_files };
  for (const t of task.visible_tests) files[t.path] = t.content;
  return Object.fromEntries(Object.entries(files).sort(([a], [b]) => a.localeCompare(b)));
}

/** The subset of `files` that may be sent to the backend. */
export function editableOnly(task: CandidateTaskView, files: Record<string, string>): Record<string, string> {
  return Object.fromEntries(Object.entries(files).filter(([p]) => isEditable(task, p)));
}
