import type { TouchedFile } from "./types";
import { changedLineCount, isDocsOnly, isLockOnly, parseUnifiedDiff } from "./diff";

const UA = "code-compr";
const MAX_DIFF_CHARS = 200_000;
const MAX_CHANGED_LINES = 120;
const MAX_FILES = 5;

export type SearchHit = {
  owner: string;
  name: string;
  number: number;
  title: string;
  body: string;
  htmlUrl: string;
  labels: string[];
  updatedAt: string;
};

export type RepoMeta = {
  stars: number;
  openIssues: number;
  pushedAt: Date | null;
  language: string;
  description: string;
};

export type ClosingPull = {
  prNumber: number;
  prUrl: string;
  baseSha: string;
  groundTruthDiff: string;
  files: TouchedFile[];
  issueBody: string;
};

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function text(url: string, attempt = 0): Promise<string | null> {
  await sleep(280);
  const response = await fetch(url, {
    headers: { "User-Agent": UA, Accept: "*/*" },
    redirect: "follow",
  });
  if (response.status === 404) return null;
  if ((response.status === 429 || response.status >= 500) && attempt < 3) {
    await sleep(1500 * (attempt + 1));
    return text(url, attempt + 1);
  }
  if (!response.ok) throw new Error(`${response.status} ${url}`);
  return response.text();
}

function githubHeaders(): HeadersInit {
  const headers: Record<string, string> = {
    Accept: "application/vnd.github+json",
    "User-Agent": UA,
    "X-GitHub-Api-Version": "2022-11-28",
  };
  const token = process.env.GITHUB_TOKEN?.trim();
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

function embeddedPayload(html: string): unknown {
  const marker = 'data-target="react-app.embeddedData">';
  const start = html.indexOf(marker);
  if (start < 0) throw new Error("GitHub page has no embedded data");
  const from = html.indexOf(">", start) + 1;
  const end = html.indexOf("</script>", from);
  return JSON.parse(html.slice(from, end));
}

function findIssue(
  payload: unknown,
  number: number,
): {
  body?: string;
  closedByPullRequestsReferences?: { nodes?: { number: number; url: string; state: string }[] };
} | null {
  const stack: unknown[] = [payload];
  while (stack.length) {
    const current = stack.pop();
    if (!current || typeof current !== "object") continue;
    const record = current as Record<string, unknown>;
    if (record.number === number && "closedByPullRequestsReferences" in record) {
      return record as {
        body?: string;
        closedByPullRequestsReferences?: { nodes?: { number: number; url: string; state: string }[] };
      };
    }
    for (const value of Object.values(record)) stack.push(value);
  }
  return null;
}

export function extractParentSha(html: string, commitSha: string): string | null {
  const parents = html.match(/"parents":\[([\s\S]*?)\]/);
  const oid = parents?.[1]?.match(/[0-9a-f]{40}/);
  if (oid && oid[0] !== commitSha) return oid[0];
  const labeled = html.match(/parent[\s\S]{0,500}?\/commit\/([0-9a-f]{40})/i);
  if (labeled && labeled[1] !== commitSha) return labeled[1];
  return null;
}

export function commitShas(html: string): string[] {
  const seen = new Set<string>();
  const ordered: string[] = [];
  const add = (sha: string) => {
    if (seen.has(sha)) return;
    seen.add(sha);
    ordered.push(sha);
  };
  for (const match of html.matchAll(/"oid"\s*:\s*"([0-9a-f]{40})"\s*,\s*"pushedDate"/g)) add(match[1]);
  for (const match of html.matchAll(/\/commit\/([0-9a-f]{40})/g)) add(match[1]);
  return ordered;
}

export async function searchClosedIssues(query: string, page: number): Promise<SearchHit[]> {
  const q = encodeURIComponent(query);
  const url = `https://api.github.com/search/issues?q=${q}&sort=updated&order=desc&per_page=10&page=${page}`;
  const response = await fetch(url, { headers: githubHeaders() });
  if (response.status === 403 || response.status === 429) {
    throw new Error("GitHub search rate limit reached");
  }
  if (!response.ok) throw new Error(`search ${response.status}`);
  const data = (await response.json()) as {
    items?: {
      number: number;
      title: string;
      body: string | null;
      html_url: string;
      updated_at: string;
      repository_url: string;
      labels: { name: string }[];
      pull_request?: unknown;
    }[];
  };
  return (data.items ?? [])
    .filter((item) => !item.pull_request && item.html_url.includes("/issues/"))
    .map((item) => {
      const [owner, name] = item.repository_url.replace("https://api.github.com/repos/", "").split("/");
      return {
        owner,
        name,
        number: item.number,
        title: item.title,
        body: item.body ?? "",
        htmlUrl: item.html_url,
        labels: item.labels.map((label) => label.name),
        updatedAt: item.updated_at,
      };
    });
}

export async function fetchSeedRepos(): Promise<Set<string>> {
  const response = await fetch(
    "https://raw.githubusercontent.com/DeepSourceCorp/good-first-issue/master/data/repositories.toml",
    { headers: { "User-Agent": UA } },
  );
  if (!response.ok) return new Set();
  const toml = await response.text();
  const names = new Set<string>();
  for (const match of toml.matchAll(/github\.com\/([A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+)/g)) {
    names.add(match[1].toLowerCase());
  }
  return names;
}

const repoCache = new Map<string, RepoMeta>();

export async function fetchRepoMeta(owner: string, name: string): Promise<RepoMeta> {
  const key = `${owner}/${name}`.toLowerCase();
  const cached = repoCache.get(key);
  if (cached) return cached;

  const response = await fetch(`https://api.github.com/repos/${owner}/${name}`, {
    headers: githubHeaders(),
  });
  if (response.status === 403 || response.status === 429) {
    throw new Error("GitHub core rate limit reached");
  }
  if (!response.ok) throw new Error(`repo ${response.status} ${owner}/${name}`);
  const data = (await response.json()) as {
    stargazers_count: number;
    open_issues_count: number;
    pushed_at: string | null;
    language: string | null;
    description: string | null;
  };
  const meta: RepoMeta = {
    stars: data.stargazers_count ?? 0,
    openIssues: data.open_issues_count ?? 0,
    pushedAt: data.pushed_at ? new Date(data.pushed_at) : null,
    language: data.language ?? "",
    description: data.description ?? "",
  };
  repoCache.set(key, meta);
  return meta;
}

export function passesRepoBar(meta: RepoMeta): string | null {
  if (!meta.pushedAt) return "repository has no push date";
  const cutoff = Date.now() - 180 * 24 * 60 * 60 * 1000;
  if (meta.pushedAt.getTime() < cutoff) return "repository has no commit in 180 days";
  if (meta.openIssues > 1000 && meta.stars < 100) {
    return "repository looks like an automated issue dump";
  }
  return null;
}

export async function loadClosingPull(
  hit: SearchHit,
): Promise<{ pull: ClosingPull } | { reason: string }> {
  const issueHtml = await text(hit.htmlUrl);
  if (!issueHtml) return { reason: "issue page missing" };
  let issue: ReturnType<typeof findIssue>;
  try {
    issue = findIssue(embeddedPayload(issueHtml), hit.number);
  } catch (error) {
    return { reason: (error as Error).message };
  }
  const nodes = issue?.closedByPullRequestsReferences?.nodes ?? [];
  const merged = [...nodes].reverse().find((node) => node.state === "MERGED");
  if (!merged) return { reason: "no merged pull" };

  const diff = await text(`https://github.com/${hit.owner}/${hit.name}/pull/${merged.number}.diff`);
  if (!diff || diff.length > MAX_DIFF_CHARS || !diff.includes("diff --git")) {
    return { reason: "diff missing or too large" };
  }
  const files = parseUnifiedDiff(diff);
  const lines = changedLineCount(files);
  if (files.length < 1 || files.length > MAX_FILES) return { reason: `${files.length} files` };
  if (lines > MAX_CHANGED_LINES || lines < 1) return { reason: `${lines} changed lines` };
  if (isDocsOnly(files) || isLockOnly(files)) return { reason: "docs or lockfile only" };

  const commitsHtml = await text(`https://github.com/${hit.owner}/${hit.name}/pull/${merged.number}/commits`);
  if (!commitsHtml) return { reason: "commits page missing" };
  const shas = commitShas(commitsHtml);
  const earliest = shas.at(-1);
  if (!earliest) return { reason: "no commit sha" };
  const commitHtml = await text(`https://github.com/${hit.owner}/${hit.name}/commit/${earliest}`);
  if (!commitHtml) return { reason: "commit page missing" };
  const baseSha = extractParentSha(commitHtml, earliest);
  if (!baseSha) return { reason: "no parent sha" };

  return {
    pull: {
      prNumber: merged.number,
      prUrl: merged.url || `https://github.com/${hit.owner}/${hit.name}/pull/${merged.number}`,
      baseSha,
      groundTruthDiff: diff,
      files,
      issueBody: issue?.body?.trim() ? issue.body : hit.body,
    },
  };
}
