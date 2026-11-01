"""Analyze a GitHub repository into an evidence-based technical report.

Usage:
    python github_repo_analysis/analyze.py https://github.com/owner/repo
    python github_repo_analysis/analyze.py https://github.com/owner/repo --stdout
    python github_repo_analysis/analyze.py --path ./local-repo
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import requests

from collect import analyze_tree
from report import render_markdown

TIMEOUT = 30
CLONE_TIMEOUT = 180
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
HERE = Path(__file__).resolve().parent
DEFAULT_OUTPUT = HERE / "reports"


class AnalyzeError(Exception):
    """Raised when the repository URL cannot be analyzed."""


def parse_repo_url(text: str) -> dict:
    raw = text.strip().strip("\"'")
    if not raw:
        raise AnalyzeError("Paste a GitHub repository URL.")
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    parsed = urlparse(raw)
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host != "github.com":
        raise AnalyzeError("That link is not a GitHub repository URL. Use https://github.com/owner/repo")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        raise AnalyzeError(
            "That URL does not include a repository. Use a link like https://github.com/owner/repo"
        )
    owner, repo = parts[0], parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", owner) or not re.fullmatch(r"[A-Za-z0-9_.-]+", repo):
        raise AnalyzeError("Could not read the owner or repository name from that URL.")
    branch = None
    if len(parts) >= 4 and parts[2] in {"tree", "blob"}:
        branch = parts[3]
    return {
        "owner": owner,
        "repo": repo,
        "branch": branch,
        "url": f"https://github.com/{owner}/{repo}",
        "clone_url": f"https://github.com/{owner}/{repo}.git",
    }


def _github_metadata(owner: str, repo: str) -> tuple[dict | None, str | None]:
    try:
        response = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}",
            headers={"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT},
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        return None, f"GitHub API was not reachable ({exc})."
    if response.status_code == 404:
        return None, "GitHub API returned 404. The repository may be private or missing. Clone will still be attempted."
    if response.status_code != 200:
        return None, f"GitHub API returned HTTP {response.status_code}. Metadata from the API was skipped."
    payload = response.json()
    parent = payload.get("parent") or {}
    license_info = payload.get("license") or {}
    return {
        "description": payload.get("description"),
        "primary_language": payload.get("language"),
        "topics": payload.get("topics") or [],
        "fork": bool(payload.get("fork")),
        "parent": parent.get("full_name"),
        "default_branch": payload.get("default_branch"),
        "homepage": payload.get("homepage"),
        "stars": payload.get("stargazers_count"),
        "forks": payload.get("forks_count"),
        "open_issues": payload.get("open_issues_count"),
        "size_kb": payload.get("size"),
        "license": license_info.get("spdx_id") or license_info.get("name"),
        "created_at": payload.get("created_at"),
        "pushed_at": payload.get("pushed_at"),
        "archived": bool(payload.get("archived")),
    }, None


def _clone(meta: dict, github: dict | None, dest: Path) -> str:
    if shutil.which("git") is None:
        raise AnalyzeError("git is not installed, so the repository could not be cloned.")
    branch = meta.get("branch") or (github or {}).get("default_branch")
    size_kb = (github or {}).get("size_kb") or 0
    command = ["git", "clone", "--quiet"]
    note = "Full clone."
    if size_kb and size_kb > 100_000:
        command.extend(["--depth", "300"])
        note = "Clone depth was limited to 300 commits because GitHub reports this repository as larger than 100 MB."
    if branch:
        command.extend(["--branch", branch, "--single-branch"])
        note += f" Branch: {branch}."
    command.extend([meta["clone_url"], str(dest)])
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=CLONE_TIMEOUT,
        )
    except subprocess.TimeoutExpired as exc:
        raise AnalyzeError("Cloning the repository took too long and was stopped.") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        lowered = detail.lower()
        if "not found" in lowered or "repository not found" in lowered or "403" in lowered or "authentication" in lowered:
            raise AnalyzeError(
                "The repository is not accessible. It may be private, missing, or blocked."
            )
        raise AnalyzeError(detail or "git clone failed.")
    return note


def _write_outputs(analysis: dict, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    source = analysis["source"]
    stem = f"{source['owner']}__{source['repo']}"
    markdown_path = output_dir / f"{stem}.md"
    json_path = output_dir / f"{stem}.json"
    markdown_path.write_text(render_markdown(analysis), encoding="utf-8")
    json_path.write_text(json.dumps(analysis, indent=2, ensure_ascii=False), encoding="utf-8")
    return markdown_path, json_path


def analyze(url: str | None = None, path: str | None = None, output_dir: Path | None = None) -> tuple[dict, Path, Path]:
    output_dir = output_dir or DEFAULT_OUTPUT
    if path:
        local = Path(path).resolve()
        if not local.is_dir():
            raise AnalyzeError(f"Folder not found: {local}")
        meta = {
            "owner": local.parent.name,
            "repo": local.name,
            "branch": None,
            "url": str(local),
            "clone_url": "",
        }
        github, api_error = (None, "Local folder: GitHub API metadata was not requested.")
        analysis = analyze_tree(local, meta, github, api_error, "Local folder. Nothing was cloned.")
        markdown_path, json_path = _write_outputs(analysis, output_dir)
        return analysis, markdown_path, json_path

    if not url:
        raise AnalyzeError("Pass a GitHub repository URL or --path.")
    meta = parse_repo_url(url)
    github, api_error = _github_metadata(meta["owner"], meta["repo"])
    with tempfile.TemporaryDirectory(prefix="repo-analysis-") as tmp:
        dest = Path(tmp) / "repo"
        note = _clone(meta, github, dest)
        analysis = analyze_tree(dest, meta, github, api_error, note)
    markdown_path, json_path = _write_outputs(analysis, output_dir)
    return analysis, markdown_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze a GitHub repository and write a technical interview report.")
    parser.add_argument("url", nargs="?", help="GitHub repository URL")
    parser.add_argument("--path", help="Analyze a local repository folder instead of cloning")
    parser.add_argument("--stdout", action="store_true", help="Print the full Markdown report")
    parser.add_argument("--output-dir", help="Folder for the Markdown and JSON reports")
    args = parser.parse_args(argv)
    if not args.url and not args.path:
        args.url = input("Paste a GitHub repository URL: ").strip()
    output = Path(args.output_dir).resolve() if args.output_dir else DEFAULT_OUTPUT
    try:
        analysis, markdown_path, json_path = analyze(args.url, args.path, output)
    except AnalyzeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    source = analysis["source"]
    print(f"Repository: {source['url']}")
    print(f"Primary language: {analysis.get('primary_language') or 'Not identified'}")
    print(f"Report: {markdown_path}")
    print(f"JSON: {json_path}")
    if args.stdout:
        print()
        print(markdown_path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
