import { buildComprehensionQuestions, readmeExcerpt } from "./curate";
import type { SnapshotFile } from "./types";

// One bundled sample task. The full code-compr app ingests closed GitHub issues
// that have a linked PR (scripts/ingest.ts), snapshots the repo at the PR's base
// commit and keeps the PR diff as the reference. A static page can't do that, so
// this is a small hand-written repo in the same shape: snapshot, issue, the closing
// diff and the files it touched. The questions are still built by curate.ts.

const README = `# pagekit

Small helpers for paginating lists in server-rendered views.

    from pagekit import paginate, page_links

    page = paginate(rows, page=2, per_page=20)
    links = page_links(rows, current=2, per_page=20)

Pages are numbered from 1. Asking for a page past the end returns the last page.
`;

const INIT = `from .paginate import Page, paginate
from .links import page_links

__all__ = ["Page", "paginate", "page_links"]
`;

const PAGINATE = `"""Split a list into numbered pages."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Page:
    items: list
    page: int
    pages: int
    has_next: bool


def paginate(items, page=1, per_page=10):
    """Return one page of items. Pages are numbered from 1."""
    if per_page < 1:
        raise ValueError("per_page must be at least 1")
    if not items:
        return Page(items=[], page=1, pages=0, has_next=False)

    pages = len(items) // per_page
    page = max(1, min(page, pages))
    start = (page - 1) * per_page
    return Page(
        items=items[start:start + per_page],
        page=page,
        pages=pages,
        has_next=page < pages,
    )
`;

const LINKS = `"""Build the page links shown under a list view."""
from .paginate import paginate


def page_links(items, current, per_page=10):
    """Return (number, url, is_current) for every page."""
    links = []
    total = paginate(list(items), current, per_page).pages
    for number in range(1, total + 1):
        page = paginate(list(items), number, per_page)
        links.append((number, f"?page={number}", page.page == current))
    return links
`;

const TESTS = `import pytest

from pagekit import paginate, page_links


def test_exact_multiple():
    page = paginate(list(range(6)), page=2, per_page=3)
    assert page.items == [3, 4, 5]
    assert page.pages == 2
    assert not page.has_next


def test_empty():
    page = paginate([], page=1, per_page=3)
    assert page.items == []
    assert page.pages == 0


def test_page_past_the_end_clamps():
    page = paginate(list(range(6)), page=9, per_page=3)
    assert page.page == 2


def test_rejects_zero_per_page():
    with pytest.raises(ValueError):
        paginate([1], per_page=0)


def test_links_mark_current():
    links = page_links(list(range(6)), current=1, per_page=3)
    assert [n for n, _, on in links if on] == [1]
`;

const SNAPSHOT: SnapshotFile[] = [
  { path: "README.md", content: README },
  { path: "pagekit/__init__.py", content: INIT },
  { path: "pagekit/paginate.py", content: PAGINATE },
  { path: "pagekit/links.py", content: LINKS },
  { path: "tests/test_paginate.py", content: TESTS },
];

const ISSUE_BODY = `With 7 items and per_page=3, paginate reports 2 pages and the seventh item never appears on any page. page_links also stops at page 2.

With fewer items than per_page (say 2 items, per_page=10), pages comes back as 0 even though page 1 has items, so templates that hide the pager when pages is 0 also hide the only page link.

Expected: 7 items at 3 per page gives 3 pages, and the last page holds the one remaining item.`;

// The closing change, kept as the reference. Only the rubric reads it.
const GROUND_TRUTH_DIFF = `diff --git a/pagekit/paginate.py b/pagekit/paginate.py
--- a/pagekit/paginate.py
+++ b/pagekit/paginate.py
@@ -18,7 +18,7 @@ def paginate(items, page=1, per_page=10):
         return Page(items=[], page=1, pages=0, has_next=False)

-    pages = len(items) // per_page
+    pages = (len(items) + per_page - 1) // per_page
     page = max(1, min(page, pages))
     start = (page - 1) * per_page
     return Page(`;

const TOUCHED = ["pagekit/paginate.py"];
const TITLE = "Last page is dropped when the item count isn't a multiple of per_page";

export const TASK = {
  repo: "pagekit (sample)",
  language: "Python",
  issueNumber: 42,
  title: TITLE,
  issueBody: ISSUE_BODY,
  snapshot: SNAPSHOT,
  groundTruthDiff: GROUND_TRUTH_DIFF,
  touchedPaths: TOUCHED,
  readmeExcerpt: readmeExcerpt(SNAPSHOT),
  questions: buildComprehensionQuestions(TITLE, ISSUE_BODY, SNAPSHOT, TOUCHED),
};

/** What the scripted assistant says about each file when it's named. */
export const FILE_NOTES: Record<string, string> = {
  "README.md": "The README shows the public API: paginate(rows, page, per_page) and page_links(rows, current, per_page). It also promises that a page past the end returns the last page.",
  "pagekit/__init__.py": "__init__.py only re-exports Page, paginate and page_links. Nothing to fix there.",
  "pagekit/paginate.py": "paginate validates per_page, returns an empty Page for empty input, then computes pages, clamps the requested page into 1..pages and slices. Every other value depends on how pages is computed, so read that line closely.",
  "pagekit/links.py": "page_links asks paginate for the page count, then calls paginate again for every page number just to build one tuple each. It also copies the input with list(items) on each call.",
  "tests/test_paginate.py": "The tests cover an exact multiple (6 items, 3 per page), empty input, clamping and per_page=0. None of them use a count that leaves a partial last page, which is why the bug got through.",
};
