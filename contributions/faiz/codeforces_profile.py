"""Fetch public Codeforces stats from a profile link.

Usage:
    python codeforces_profile.py https://codeforces.com/profile/handle
    python codeforces_profile.py https://codeforces.com/profile/handle --json
    python codeforces_profile.py

Uses the public Codeforces API (user.info, user.rating, user.status).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlparse

import requests

TIMEOUT = 60
PAUSE_SECONDS = 2.0
PAGE_SIZE = 10000
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
HANDLE_RE = re.compile(r"[A-Za-z0-9_.-]{1,24}")
_last_call = 0.0


class CodeforcesError(Exception):
    """Raised when a profile link cannot be resolved or Codeforces rejects the request."""


def parse_profile_link(text: str) -> str:
    """Return a handle from a Codeforces profile link or a bare handle."""
    raw = text.strip().strip("\"'")
    if not raw:
        raise CodeforcesError("Paste a Codeforces profile link.")

    if HANDLE_RE.fullmatch(raw):
        return raw

    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw

    parsed = urlparse(raw)
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host != "codeforces.com" and not host.endswith(".codeforces.com"):
        raise CodeforcesError(
            "That link is not a Codeforces profile. Use a link like https://codeforces.com/profile/handle"
        )

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) >= 2 and parts[0] in {"profile", "submissions"}:
        handle = parts[1]
    elif parts:
        handle = parts[0]
    else:
        raise CodeforcesError("Could not find a handle in that link.")

    if not HANDLE_RE.fullmatch(handle):
        raise CodeforcesError(f"'{handle}' is not a valid Codeforces handle.")
    return handle


def _api(method: str, **params):
    global _last_call
    wait = PAUSE_SECONDS - (time.monotonic() - _last_call)
    if _last_call and wait > 0:
        time.sleep(wait)

    last_comment = "Codeforces did not return any data."
    for attempt in range(4):
        try:
            response = requests.get(
                f"https://codeforces.com/api/{method}",
                params=params,
                headers={"User-Agent": USER_AGENT},
                timeout=TIMEOUT,
            )
        except requests.RequestException as exc:
            raise CodeforcesError(f"Could not reach Codeforces ({exc}).") from exc
        _last_call = time.monotonic()

        try:
            payload = response.json()
        except ValueError as exc:
            raise CodeforcesError(f"Codeforces returned HTTP {response.status_code}.") from exc

        if payload.get("status") == "OK":
            return payload.get("result")

        last_comment = payload.get("comment") or last_comment
        if "limit" in last_comment.lower() and attempt < 3:
            time.sleep(PAUSE_SECONDS * (attempt + 2))
            continue
        break

    if "not found" in last_comment.lower():
        handle = params.get("handle") or params.get("handles") or "that user"
        raise CodeforcesError(f"No Codeforces user named '{handle}'.")
    raise CodeforcesError(last_comment)


def _language_name(raw: str) -> str:
    name = (raw or "Unknown").split("(")[0].strip() or "Unknown"
    lowered = name.lower()
    if "c++" in lowered:
        return "C++"
    if lowered.startswith("python") or lowered.startswith("pypy"):
        return "Python"
    if lowered == "java" or lowered.startswith("java "):
        return "Java"
    if lowered == "c" or lowered.startswith("gnu c"):
        return "C"
    if lowered.startswith("c#"):
        return "C#"
    if lowered.startswith("kotlin"):
        return "Kotlin"
    return name


def _problem_id(problem: dict) -> str:
    contest_id = problem.get("contestId")
    index = problem.get("index")
    if contest_id is not None and index:
        return f"{contest_id}{index}"
    return problem.get("name") or "unknown"


def _band(rating: int | None) -> str:
    if rating is None:
        return "unrated"
    if rating < 1200:
        return "up_to_1199"
    if rating < 1600:
        return "1200_1599"
    if rating < 2000:
        return "1600_1999"
    return "2000_plus"


def _streaks(days: set[date]) -> tuple[int, int]:
    if not days:
        return 0, 0
    ordered = sorted(days)
    best = 1
    run = 1
    for previous, current in zip(ordered, ordered[1:]):
        if current - previous == timedelta(days=1):
            run += 1
            best = max(best, run)
        else:
            run = 1

    today = datetime.now(timezone.utc).date()
    if today in days:
        anchor = today
    elif today - timedelta(days=1) in days:
        anchor = today - timedelta(days=1)
    else:
        anchor = None

    current_streak = 0
    while anchor is not None and anchor in days:
        current_streak += 1
        anchor -= timedelta(days=1)
    return best, current_streak


def _submissions(handle: str) -> list[dict]:
    rows: list[dict] = []
    start = 1
    while True:
        page = _api("user.status", handle=handle, **{"from": start, "count": PAGE_SIZE}) or []
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows
        start += PAGE_SIZE


def fetch_profile(link: str) -> dict:
    handle = parse_profile_link(link)
    info = (_api("user.info", handles=handle) or [None])[0]
    if not info:
        raise CodeforcesError(f"No Codeforces user named '{handle}'.")

    handle = info.get("handle") or handle
    contests = _api("user.rating", handle=handle) or []
    submissions = _submissions(handle)

    solved: dict[str, dict] = {}
    languages: dict[str, set[str]] = defaultdict(set)
    active_days: set[date] = set()

    for submission in submissions:
        stamp = submission.get("creationTimeSeconds")
        if stamp:
            active_days.add(datetime.fromtimestamp(int(stamp), tz=timezone.utc).date())
        if submission.get("verdict") != "OK":
            continue
        problem = submission.get("problem") or {}
        problem_id = _problem_id(problem)
        rating = problem.get("rating")
        entry = solved.setdefault(
            problem_id,
            {
                "rating": int(rating) if rating is not None else None,
                "tags": list(problem.get("tags") or []),
            },
        )
        if entry["rating"] is None and rating is not None:
            entry["rating"] = int(rating)
        languages[_language_name(submission.get("programmingLanguage") or "")].add(problem_id)

    bands = {"up_to_1199": 0, "1200_1599": 0, "1600_1999": 0, "2000_plus": 0, "unrated": 0}
    tag_counts: dict[str, int] = defaultdict(int)
    for problem in solved.values():
        bands[_band(problem["rating"])] += 1
        for tag in problem["tags"]:
            tag_counts[tag] += 1

    language_rows = [
        {"language": name, "problems_solved": len(problems)}
        for name, problems in languages.items()
    ]
    language_rows.sort(key=lambda row: (-row["problems_solved"], row["language"].lower()))
    tag_rows = [
        {"name": name, "problems_solved": count}
        for name, count in tag_counts.items()
    ]
    tag_rows.sort(key=lambda row: (-row["problems_solved"], row["name"].lower()))

    max_streak, current_streak = _streaks(active_days)
    full_name = " ".join(
        part for part in (info.get("firstName"), info.get("lastName")) if part
    ).strip()

    return {
        "name": full_name or handle,
        "handle": handle,
        "profile_url": f"https://codeforces.com/profile/{handle}",
        "rank": info.get("rank") or "unrated",
        "rating": info.get("rating"),
        "max_rank": info.get("maxRank") or "unrated",
        "max_rating": info.get("maxRating"),
        "contribution": info.get("contribution"),
        "contests": len(contests),
        "problems_solved": {"all": len(solved), **bands},
        "languages": language_rows,
        "tags": tag_rows,
        "total_active_days": len(active_days),
        "max_streak": max_streak,
        "current_streak": current_streak,
    }


def _comma(value) -> str:
    if value is None:
        return "N/A"
    return f"{value:,}"


def _title(value: str) -> str:
    return value[:1].upper() + value[1:] if value else value


def format_report(stats: dict) -> str:
    solved = stats["problems_solved"]
    lines = [
        f"Name: {stats['name']}",
        f"Handle: {stats['handle']}",
        f"Profile: {stats['profile_url']}",
        f"Rank: {_title(stats['rank'])}",
        f"Rating: {_comma(stats['rating'])}",
        f"Max rank: {_title(stats['max_rank'])}",
        f"Max rating: {_comma(stats['max_rating'])}",
        f"Contribution: {_comma(stats['contribution'])}",
        f"Rated contests: {_comma(stats['contests'])}",
        "",
        f"Problems solved: {_comma(solved['all'])}",
        f"  Up to 1199: {_comma(solved['up_to_1199'])}",
        f"  1200-1599: {_comma(solved['1200_1599'])}",
        f"  1600-1999: {_comma(solved['1600_1999'])}",
        f"  2000 and above: {_comma(solved['2000_plus'])}",
        f"  Unrated: {_comma(solved['unrated'])}",
        "",
        "Programming languages:",
    ]
    if stats["languages"]:
        for row in stats["languages"]:
            lines.append(f"  {row['language']}: {_comma(row['problems_solved'])}")
    else:
        lines.append("  None")

    lines.append("")
    lines.append("Problem tags:")
    lines.append("  One problem can count toward more than one tag.")
    if stats["tags"]:
        for tag in stats["tags"]:
            lines.append(f"  {tag['name']}: {_comma(tag['problems_solved'])}")
    else:
        lines.append("  None")

    lines.extend(
        [
            "",
            f"Total active days: {_comma(stats['total_active_days'])}",
            f"Max streak: {_comma(stats['max_streak'])} days",
            f"Current streak: {_comma(stats['current_streak'])} days",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch public Codeforces profile stats.")
    parser.add_argument("link", nargs="?", help="Codeforces profile link, or a handle")
    parser.add_argument("--json", action="store_true", help="Print raw JSON instead of a text report")
    args = parser.parse_args(argv)

    link = args.link
    if not link:
        link = input("Paste a Codeforces profile link: ").strip()

    try:
        stats = fetch_profile(link)
    except CodeforcesError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(stats, indent=2))
    else:
        print(format_report(stats))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
