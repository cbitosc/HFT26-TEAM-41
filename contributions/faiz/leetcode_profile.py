"""Fetch public LeetCode stats from a profile link using GraphQL.

Usage:
    python leetcode_profile.py https://leetcode.com/u/username
    python leetcode_profile.py https://leetcode.com/u/username --json
    python leetcode_profile.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlparse

import requests

TIMEOUT = 30
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

PROFILE_QUERY = """
query userPublicProfile($username: String!) {
  matchedUser(username: $username) {
    username
    profile {
      ranking
      realName
    }
    submitStatsGlobal {
      acSubmissionNum {
        difficulty
        count
      }
    }
    languageProblemCount {
      languageName
      problemsSolved
    }
    tagProblemCounts {
      advanced {
        tagName
        problemsSolved
      }
      intermediate {
        tagName
        problemsSolved
      }
      fundamental {
        tagName
        problemsSolved
      }
    }
  }
}
"""


class LeetCodeError(Exception):
    """Raised when a profile link cannot be resolved or LeetCode rejects the query."""


def parse_profile_link(text: str) -> tuple[str, str]:
    """Return (graphql_endpoint, username) from a profile link or bare username."""
    raw = text.strip().strip("\"'")
    if not raw:
        raise LeetCodeError("Paste a LeetCode profile link.")

    if re.fullmatch(r"[A-Za-z0-9_-]+", raw):
        return "https://leetcode.com/graphql", raw

    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw

    parsed = urlparse(raw)
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host not in {"leetcode.com", "leetcode.cn"}:
        raise LeetCodeError(
            "That link is not a LeetCode profile. Use a link like https://leetcode.com/u/username"
        )

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) >= 2 and parts[0] == "u":
        username = parts[1]
    elif parts:
        username = parts[0]
    else:
        raise LeetCodeError("Could not find a username in that link.")

    if not re.fullmatch(r"[A-Za-z0-9_-]+", username):
        raise LeetCodeError(f"'{username}' is not a valid LeetCode username.")

    return f"https://{host}/graphql", username


def graphql(endpoint: str, username: str, query: str, variables: dict | None = None) -> dict:
    site = endpoint.removesuffix("/graphql")
    response = requests.post(
        endpoint,
        json={"query": query, "variables": variables or {"username": username}},
        headers={
            "Content-Type": "application/json",
            "Referer": f"{site}/{username}/",
            "Origin": site,
            "User-Agent": USER_AGENT,
        },
        timeout=TIMEOUT,
    )
    if response.status_code != 200:
        raise LeetCodeError(f"LeetCode returned HTTP {response.status_code}.")
    payload = response.json()
    errors = payload.get("errors") or []
    fatal = [
        error.get("message", "Unknown GraphQL error")
        for error in errors
        if not (error.get("extensions") or {}).get("handled")
    ]
    if fatal and not payload.get("data"):
        raise LeetCodeError(fatal[0])
    return payload.get("data") or {}


def _calendar_query(years: list[int]) -> str:
    blocks = []
    for year in years:
        blocks.append(
            f"""
            y{year}: matchedUser(username: $username) {{
              userCalendar(year: {year}) {{
                activeYears
                totalActiveDays
                submissionCalendar
              }}
            }}
            """
        )
    return "query userCalendars($username: String!) {\n" + "\n".join(blocks) + "\n}"


def _dates_from_calendar(raw: str | None) -> set[date]:
    if not raw:
        return set()
    try:
        counts = json.loads(raw)
    except json.JSONDecodeError:
        return set()
    days: set[date] = set()
    for stamp, count in counts.items():
        try:
            if int(count) <= 0:
                continue
            days.add(datetime.fromtimestamp(int(stamp), tz=timezone.utc).date())
        except (TypeError, ValueError, OSError):
            continue
    return days


def _streaks(days: set[date]) -> tuple[int, int]:
    """Return (max_streak, current_streak) in days."""
    if not days:
        return 0, 0

    ordered = sorted(days)
    max_streak = 1
    run = 1
    for previous, current in zip(ordered, ordered[1:]):
        if current - previous == timedelta(days=1):
            run += 1
            max_streak = max(max_streak, run)
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
    return max_streak, current_streak


def _skills(groups: dict | None) -> dict:
    result = {}
    for level in ("advanced", "intermediate", "fundamental"):
        tags = []
        for tag in (groups or {}).get(level) or []:
            solved = int(tag.get("problemsSolved") or 0)
            if solved <= 0:
                continue
            tags.append({"name": tag.get("tagName") or "Unknown", "problems_solved": solved})
        tags.sort(key=lambda item: (-item["problems_solved"], item["name"].lower()))
        result[level] = tags
    return result


def fetch_profile(link: str) -> dict:
    endpoint, username = parse_profile_link(link)
    data = graphql(endpoint, username, PROFILE_QUERY)
    user = data.get("matchedUser")
    if not user:
        raise LeetCodeError(f"No public LeetCode user named '{username}'.")

    profile = user.get("profile") or {}
    solved = {row["difficulty"]: int(row["count"]) for row in (user.get("submitStatsGlobal") or {}).get("acSubmissionNum") or []}
    languages = [
        {"language": row["languageName"], "problems_solved": int(row["problemsSolved"])}
        for row in user.get("languageProblemCount") or []
        if int(row.get("problemsSolved") or 0) > 0
    ]
    languages.sort(key=lambda item: (-item["problems_solved"], item["language"].lower()))

    activity = _fetch_activity(endpoint, username)
    real_name = (profile.get("realName") or "").strip()

    return {
        "username": user.get("username") or username,
        "name": real_name or user.get("username") or username,
        "rank": profile.get("ranking"),
        "problems_solved": {
            "all": solved.get("All", 0),
            "easy": solved.get("Easy", 0),
            "medium": solved.get("Medium", 0),
            "hard": solved.get("Hard", 0),
        },
        "languages": languages,
        "skills": _skills(user.get("tagProblemCounts")),
        "total_active_days": activity["total_active_days"],
        "max_streak": activity["max_streak"],
        "current_streak": activity["current_streak"],
        "profile_url": f"{endpoint.removesuffix('/graphql')}/{user.get('username') or username}/",
    }


def _fetch_activity(endpoint: str, username: str) -> dict:
    year = datetime.now(timezone.utc).year
    data = graphql(endpoint, username, _calendar_query([year]))
    node = ((data.get(f"y{year}") or {}).get("userCalendar")) or {}
    active_years = [int(item) for item in node.get("activeYears") or [] if int(item) != year]
    calendars = [_dates_from_calendar(node.get("submissionCalendar"))]

    if active_years:
        extra = graphql(endpoint, username, _calendar_query(active_years))
        for item in active_years:
            calendar = ((extra.get(f"y{item}") or {}).get("userCalendar")) or {}
            calendars.append(_dates_from_calendar(calendar.get("submissionCalendar")))

    days: set[date] = set()
    for group in calendars:
        days.update(group)
    max_streak, current_streak = _streaks(days)
    return {
        "total_active_days": len(days),
        "max_streak": max_streak,
        "current_streak": current_streak,
    }


def _comma(value) -> str:
    if value is None:
        return "N/A"
    return f"{value:,}"


def format_report(stats: dict) -> str:
    solved = stats["problems_solved"]
    lines = [
        f"Name: {stats['name']}",
        f"Username: {stats['username']}",
        f"Profile: {stats['profile_url']}",
        f"LeetCode rank: {_comma(stats['rank'])}",
        "",
        f"Problems solved: {_comma(solved['all'])}",
        f"  Easy: {_comma(solved['easy'])}",
        f"  Medium: {_comma(solved['medium'])}",
        f"  Hard: {_comma(solved['hard'])}",
        "",
        "Programming languages:",
    ]
    if stats["languages"]:
        for row in stats["languages"]:
            lines.append(f"  {row['language']}: {_comma(row['problems_solved'])}")
    else:
        lines.append("  None")

    lines.append("")
    lines.append("Skills (problems solved in each topic):")
    lines.append("  One problem can count toward more than one topic.")
    labels = (
        ("advanced", "Advanced"),
        ("intermediate", "Intermediate"),
        ("fundamental", "Fundamental"),
    )
    for key, label in labels:
        tags = stats["skills"][key]
        total = sum(tag["problems_solved"] for tag in tags)
        lines.append(f"  {label}: {len(tags)} topics, {_comma(total)} tagged solves")
        if not tags:
            lines.append("    None")
            continue
        for tag in tags:
            lines.append(f"    {tag['name']}: {_comma(tag['problems_solved'])}")

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
    parser = argparse.ArgumentParser(description="Fetch public LeetCode profile stats via GraphQL.")
    parser.add_argument("link", nargs="?", help="LeetCode profile link, or a username")
    parser.add_argument("--json", action="store_true", help="Print raw JSON instead of a text report")
    args = parser.parse_args(argv)

    link = args.link
    if not link:
        link = input("Paste a LeetCode profile link: ").strip()

    try:
        stats = fetch_profile(link)
    except LeetCodeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except requests.RequestException as exc:
        print(f"Error: Could not reach LeetCode ({exc}).", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(stats, indent=2))
    else:
        print(format_report(stats))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
