"""Fetch public GitHub profile stats from a profile link.

Usage:
    python github_profile.py https://github.com/username
    python github_profile.py https://github.com/username --json
    python github_profile.py

Commit totals are estimated from the activity mix GitHub prints on the
contribution graph (commits, pull requests, issues, and code review).
Pull requests are public pull requests the person opened. The activity
grade is calculated by this program.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from html import unescape
from urllib.parse import urlparse

import requests

TIMEOUT = 30
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
API_HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": USER_AGENT,
    "X-GitHub-Api-Version": "2022-11-28",
}
DAY_TAG_RE = re.compile(r"<td\b[^>]*ContributionCalendar-day[^>]*>", re.I)
ATTR_RE = re.compile(r'([\w:-]+)="([^"]*)"')
TOOLTIP_RE = re.compile(r"<tool-tip\b([^>]*)>(.*?)</tool-tip>", re.I | re.S)
COUNT_RE = re.compile(r"(\d+)\s+contributions?", re.I)
PERCENT_RE = re.compile(r'data-percentages="([^"]*)"')


class GitHubError(Exception):
    """Raised when a profile link cannot be resolved or GitHub rejects the request."""


def parse_profile_link(text: str) -> str:
    """Return a username from a GitHub profile link or a bare username."""
    raw = text.strip().strip("\"'")
    if not raw:
        raise GitHubError("Paste a GitHub profile link.")

    if re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", raw):
        return raw

    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw

    parsed = urlparse(raw)
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host != "github.com":
        raise GitHubError("That link is not a GitHub profile. Use a link like https://github.com/username")

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) >= 2 and parts[0] == "users":
        username = parts[1]
    elif parts:
        username = parts[0]
    else:
        raise GitHubError("Could not find a username in that link.")

    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", username):
        raise GitHubError(f"'{username}' is not a valid GitHub username.")
    return username


def _api_get(url: str, params: dict | None = None) -> requests.Response:
    try:
        response = requests.get(url, params=params, headers=API_HEADERS, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise GitHubError(f"Could not reach GitHub ({exc}).") from exc
    if response.status_code in {403, 429}:
        message = response.text.lower()
        if "rate limit" in message or response.status_code == 429:
            raise GitHubError(
                "GitHub API rate limit reached. Wait about an hour, then try again."
            )
    return response


def _load_user(username: str) -> tuple[dict, int]:
    response = _api_get(f"https://api.github.com/users/{username}")
    if response.status_code == 404:
        raise GitHubError(f"No GitHub user named '{username}'.")
    if response.status_code != 200:
        raise GitHubError(f"GitHub returned HTTP {response.status_code} for '{username}'.")
    user = response.json()
    if user.get("type") != "User":
        raise GitHubError(f"'{username}' is a GitHub organization, not a personal profile.")
    remaining = int(response.headers.get("X-RateLimit-Remaining", "0"))
    return user, remaining


def parse_contribution_html(html: str) -> tuple[dict[date, int], dict[str, int]]:
    """Read daily counts and the commits/PR/issue/review mix from a contribution page."""
    counts_by_cell: dict[str, int] = {}
    for attrs, body in TOOLTIP_RE.findall(html):
        attr = dict(ATTR_RE.findall(attrs))
        target = attr.get("for")
        if not target:
            continue
        match = COUNT_RE.search(unescape(body))
        counts_by_cell[target] = int(match.group(1)) if match else 0

    days: dict[date, int] = {}
    for tag in DAY_TAG_RE.findall(html):
        attr = dict(ATTR_RE.findall(tag))
        raw_date = attr.get("data-date")
        if not raw_date:
            continue
        if "data-count" in attr:
            count = int(attr["data-count"])
        else:
            count = counts_by_cell.get(attr.get("id", ""), 0)
        days[date.fromisoformat(raw_date)] = count

    percentages: dict[str, int] = {}
    match = PERCENT_RE.search(html)
    if match:
        try:
            loaded = json.loads(unescape(match.group(1)))
            percentages = {str(key): int(value) for key, value in loaded.items()}
        except (json.JSONDecodeError, TypeError, ValueError):
            percentages = {}
    return days, percentages


def _fetch_year(username: str, year: int) -> tuple[int, dict[date, int], dict[str, int]]:
    try:
        response = requests.get(
            f"https://github.com/users/{username}/contributions",
            params={"from": f"{year}-01-01", "to": f"{year}-12-31"},
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        raise GitHubError(f"Could not reach GitHub ({exc}).") from exc
    if response.status_code == 404:
        raise GitHubError(f"No GitHub user named '{username}'.")
    if response.status_code != 200:
        raise GitHubError(f"GitHub returned HTTP {response.status_code} for the {year} contribution graph.")
    days, percentages = parse_contribution_html(response.text)
    if not days:
        raise GitHubError(f"Could not read the {year} contribution graph.")
    return year, days, percentages


def _longest_streak(days: dict[date, int], today: date) -> int:
    active = sorted(day for day, count in days.items() if count > 0 and day <= today)
    if not active:
        return 0
    best = 1
    run = 1
    for previous, current in zip(active, active[1:]):
        if current - previous == timedelta(days=1):
            run += 1
            best = max(best, run)
        else:
            run = 1
    return best


def _slice_days(days: dict[date, int], start: date, end: date) -> dict[date, int]:
    return {day: count for day, count in days.items() if start <= day <= end}


def _share(count: int, percent: int) -> int:
    return int(round(count * percent / 100))


def _commits_and_prs(days: dict[date, int], year_mix: dict[int, dict[str, int]], today: date) -> tuple[int, int]:
    by_year: dict[int, int] = defaultdict(int)
    for day, count in days.items():
        if day <= today and count:
            by_year[day.year] += count
    commits = 0
    pull_requests = 0
    for year, count in by_year.items():
        mix = year_mix.get(year) or {}
        commits += _share(count, mix.get("Commits", 0))
        pull_requests += _share(count, mix.get("Pull requests", 0))
    return commits, pull_requests


def _scale(value: float, full_at: float, max_points: int) -> int:
    if value <= 0 or full_at <= 0:
        return 0
    return min(max_points, round(value / full_at * max_points))


def _letter(score: int) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 40:
        return "D"
    return "F"


def _activity_grade(window: dict[date, int], year_mix: dict[int, dict[str, int]], recent_prs: int, today: date, window_days: int) -> dict:
    contributions = sum(count for day, count in window.items() if day <= today)
    active_days = sum(1 for day, count in window.items() if day <= today and count > 0)
    streak = _longest_streak(window, today)
    commits, _ = _commits_and_prs(window, year_mix, today)
    parts = {
        "contributions": _scale(contributions, 500, 35),
        "active_days": _scale(active_days / window_days if window_days else 0, 0.5, 25),
        "streak": _scale(streak, 21, 15),
        "commits": _scale(commits, 400, 15),
        "pull_requests": _scale(recent_prs, 20, 10),
    }
    score = min(100, sum(parts.values()))
    return {
        "letter": _letter(score),
        "score": score,
        "window_days": window_days,
        "contributions": contributions,
        "active_days": active_days,
        "streak": streak,
        "commits": commits,
        "pull_requests": recent_prs,
        "points": parts,
        "max_points": {
            "contributions": 35,
            "active_days": 25,
            "streak": 15,
            "commits": 15,
            "pull_requests": 10,
        },
    }


def _search_count(query: str) -> int | None:
    try:
        response = _api_get("https://api.github.com/search/issues", {"q": query, "per_page": 1})
    except GitHubError:
        return None
    if response.status_code != 200:
        return None
    payload = response.json()
    if payload.get("incomplete_results"):
        return None
    return int(payload.get("total_count") or 0)


def _languages(username: str, rate_remaining: int) -> tuple[list[dict], str]:
    repos = []
    page = 1
    while page <= 10:
        response = _api_get(
            f"https://api.github.com/users/{username}/repos",
            {"per_page": 100, "page": page, "type": "owner", "sort": "updated"},
        )
        if response.status_code != 200:
            raise GitHubError(f"GitHub returned HTTP {response.status_code} while listing repositories.")
        batch = response.json()
        if not isinstance(batch, list) or not batch:
            break
        repos.extend(batch)
        rate_remaining = int(response.headers.get("X-RateLimit-Remaining", rate_remaining))
        if len(batch) < 100:
            break
        page += 1

    pool = [repo for repo in repos if not repo.get("fork")] or repos
    basis = "share of code in public repositories they own"
    selected = sorted(pool, key=lambda repo: repo.get("size") or 0, reverse=True)
    can_fetch_bytes = rate_remaining > min(len(selected), 30) + 2
    if not can_fetch_bytes:
        counts: dict[str, int] = defaultdict(int)
        for repo in pool:
            language = repo.get("language")
            if language:
                counts[language] += 1
        total = sum(counts.values()) or 1
        rows = [
            {
                "language": language,
                "repositories": count,
                "bytes": None,
                "share": round(count / total * 100, 1),
            }
            for language, count in counts.items()
        ]
        rows.sort(key=lambda row: (-row["repositories"], row["language"].lower()))
        return rows, "main language of each public repository they own"

    totals: dict[str, int] = defaultdict(int)
    repo_hits: dict[str, int] = defaultdict(int)
    looked_at = selected[:30]
    for repo in looked_at:
        response = _api_get(repo["languages_url"])
        if response.status_code != 200:
            continue
        sizes = response.json()
        if not isinstance(sizes, dict):
            continue
        seen = set()
        for language, size in sizes.items():
            amount = int(size or 0)
            if amount <= 0:
                continue
            totals[language] += amount
            seen.add(language)
        for language in seen:
            repo_hits[language] += 1
        rate_remaining = int(response.headers.get("X-RateLimit-Remaining", rate_remaining))

    total_bytes = sum(totals.values())
    if not total_bytes:
        return [], basis
    if len(pool) > len(looked_at):
        basis = f"share of code in the {len(looked_at)} largest public repositories they own"
    rows = [
        {
            "language": language,
            "repositories": repo_hits[language],
            "bytes": amount,
            "share": round(amount / total_bytes * 100, 1),
        }
        for language, amount in totals.items()
    ]
    rows.sort(key=lambda row: (-row["bytes"], row["language"].lower()))
    return rows, basis


def fetch_profile(link: str) -> dict:
    username = parse_profile_link(link)
    user, rate_remaining = _load_user(username)
    login = user.get("login") or username
    joined = datetime.fromisoformat(user["created_at"].replace("Z", "+00:00")).date()
    today = datetime.now(timezone.utc).date()
    years = list(range(joined.year, today.year + 1))

    year_mix: dict[int, dict[str, int]] = {}
    days: dict[date, int] = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(_fetch_year, login, year) for year in years]
        for future in as_completed(futures):
            year, year_days, percentages = future.result()
            year_mix[year] = percentages
            days.update(year_days)

    contributions = sum(count for day, count in days.items() if day <= today)
    total_commits, _ = _commits_and_prs(days, year_mix, today)
    span_days = max(1, (today - joined).days + 1)
    longest = _longest_streak(days, today)

    window_start = max(joined, today - timedelta(days=364))
    window_days = max(1, (today - window_start).days + 1)
    window = _slice_days(days, window_start, today)
    recent_contributions = sum(window.values())

    all_prs = _search_count(f"author:{login} type:pr")
    recent_prs = _search_count(f"author:{login} type:pr created:>={window_start.isoformat()}")
    grade = _activity_grade(window, year_mix, recent_prs or 0, today, window_days)

    languages, language_basis = _languages(login, rate_remaining)

    name = (user.get("name") or "").strip() or login
    return {
        "name": name,
        "username": login,
        "profile_url": user.get("html_url") or f"https://github.com/{login}",
        "joined": joined.isoformat(),
        "contributions": contributions,
        "contributions_last_365_days": recent_contributions,
        "languages": languages,
        "language_basis": language_basis,
        "total_repos": int(user.get("public_repos") or 0),
        "longest_streak": longest,
        "avg_commits_per_day": round(total_commits / span_days, 2),
        "total_commits": total_commits,
        "commits_estimated": True,
        "pull_requests": all_prs,
        "activity_grade": grade,
    }


def _comma(value) -> str:
    if value is None:
        return "Unavailable"
    return f"{value:,}"


def format_report(stats: dict) -> str:
    grade = stats["activity_grade"]
    points = grade["points"]
    maximum = grade["max_points"]
    lines = [
        f"Name: {stats['name']}",
        f"Username: {stats['username']}",
        f"Profile: {stats['profile_url']}",
        "",
        f"Contributions: {_comma(stats['contributions'])}",
        f"  Last {grade['window_days']} days: {_comma(stats['contributions_last_365_days'])}",
        "",
        "Languages:",
    ]
    visible = [row for row in stats["languages"] if row["share"] >= 0.1] or stats["languages"][:5]
    hidden = len(stats["languages"]) - len(visible)
    if visible:
        lines.append(f"  ({stats['language_basis']})")
        for row in visible:
            repos = row["repositories"]
            repo_label = "repo" if repos == 1 else "repos"
            if row["bytes"] is None:
                lines.append(f"  {row['language']}: {row['share']}% ({repos} {repo_label})")
            else:
                lines.append(
                    f"  {row['language']}: {row['share']}% ({_comma(row['bytes'])} bytes, {repos} {repo_label})"
                )
        if hidden:
            lines.append(f"  plus {hidden} smaller languages")
    else:
        lines.append("  None in public repositories")

    lines.extend(
        [
            "",
            f"Total public repos: {_comma(stats['total_repos'])}",
            f"Longest streak: {_comma(stats['longest_streak'])} days",
            f"Average commits per day: {stats['avg_commits_per_day']}",
            f"Total commits: {_comma(stats['total_commits'])} (estimated)",
            f"Pull requests: {_comma(stats['pull_requests'])}",
            "",
            f"Activity grade: {grade['letter']} ({grade['score']}/100)",
            (
                f"  Last {grade['window_days']} days: "
                f"contributions {points['contributions']}/{maximum['contributions']}, "
                f"active days {points['active_days']}/{maximum['active_days']}, "
                f"streak {points['streak']}/{maximum['streak']}, "
                f"commits {points['commits']}/{maximum['commits']}, "
                f"pull requests {points['pull_requests']}/{maximum['pull_requests']}"
            ),
            "  Full marks: 500 contributions, activity on half the days, a 21-day streak, 400 commits, and 20 pull requests.",
            "  This grade is calculated here. GitHub does not publish an official activity grade.",
            "  Commit counts are estimated from the mix of commits, pull requests, issues, and reviews on the contribution graph.",
            "  The average is total estimated commits divided by days since the account was created.",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch public GitHub profile stats.")
    parser.add_argument("link", nargs="?", help="GitHub profile link, or a username")
    parser.add_argument("--json", action="store_true", help="Print raw JSON instead of a text report")
    args = parser.parse_args(argv)

    link = args.link
    if not link:
        link = input("Paste a GitHub profile link: ").strip()

    try:
        stats = fetch_profile(link)
    except GitHubError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(stats, indent=2))
    else:
        print(format_report(stats))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
