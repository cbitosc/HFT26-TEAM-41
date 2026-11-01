import type { SnapshotFile, TouchedFile } from "./types";

const SOURCE = /\.(py|js|mjs|cjs|ts|tsx|jsx|go|rb|java|rs|c|cc|cpp|h|hpp|cs|php|kt|swift|scala|lua|vue|svelte)$/i;
const MAX_FILES = 24;
const MAX_CHARS = 50_000;

function clip(content: string): string {
  if (content.length <= MAX_CHARS) return content;
  return `${content.slice(0, MAX_CHARS)}\n\n/* snapshot truncated */\n`;
}

function encodePath(path: string): string {
  return path.split("/").map(encodeURIComponent).join("/");
}

export async function fetchRaw(
  owner: string,
  repo: string,
  sha: string,
  path: string,
): Promise<string | null> {
  const url = `https://raw.githubusercontent.com/${owner}/${repo}/${sha}/${encodePath(path)}`;
  const response = await fetch(url, {
    headers: { "User-Agent": "code-compr", Accept: "text/plain,*/*" },
  });
  if (!response.ok) return null;
  const text = await response.text();
  if (text.includes("\u0000")) return null;
  if (/^404: Not Found\s*$/.test(text.trim())) return null;
  return text;
}

async function listSiblings(
  owner: string,
  repo: string,
  sha: string,
  directory: string,
): Promise<string[]> {
  const url = directory
    ? `https://github.com/${owner}/${repo}/tree/${sha}/${encodePath(directory)}`
    : `https://github.com/${owner}/${repo}/tree/${sha}`;
  const response = await fetch(url, {
    headers: { "User-Agent": "code-compr", Accept: "text/html" },
  });
  if (!response.ok) return [];
  const html = await response.text();
  const paths = new Set<string>();
  for (const match of html.matchAll(/\/blob\/[0-9a-f]{40}\/([^"#?\s]+)/g)) {
    const path = decodeURIComponent(match[1]);
    const folder = path.includes("/") ? path.slice(0, path.lastIndexOf("/")) : "";
    if (folder !== directory) continue;
    if (!SOURCE.test(path)) continue;
    paths.add(path);
  }
  return [...paths];
}

export async function materializeSnapshot(
  owner: string,
  repo: string,
  sha: string,
  touched: TouchedFile[],
): Promise<SnapshotFile[]> {
  const files: SnapshotFile[] = [];
  const seen = new Set<string>();

  const add = (path: string, content: string | null) => {
    if (content == null || seen.has(path) || files.length >= MAX_FILES) return;
    seen.add(path);
    files.push({ path, content: clip(content) });
  };

  for (const readmeName of ["README.md", "README.rst", "README"]) {
    const readme = await fetchRaw(owner, repo, sha, readmeName);
    if (readme) {
      add(readmeName, readme);
      break;
    }
  }

  for (const file of touched) {
    if (file.status === "added") continue;
    add(file.path, await fetchRaw(owner, repo, sha, file.path));
  }

  const directories = [
    ...new Set(
      touched.map((file) => {
        const index = file.path.lastIndexOf("/");
        return index === -1 ? "" : file.path.slice(0, index);
      }),
    ),
  ];

  for (const directory of directories) {
    if (files.length >= MAX_FILES) break;
    let siblings: string[] = [];
    try {
      siblings = await listSiblings(owner, repo, sha, directory);
    } catch {
      siblings = [];
    }
    let added = 0;
    for (const sibling of siblings) {
      if (added >= 3 || files.length >= MAX_FILES) break;
      if (seen.has(sibling)) continue;
      const content = await fetchRaw(owner, repo, sha, sibling);
      if (!content) continue;
      add(sibling, content);
      added += 1;
    }
  }

  return files;
}
