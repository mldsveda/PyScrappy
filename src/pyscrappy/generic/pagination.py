"""Automatic pagination detection."""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

_NEXT_PATTERNS = re.compile(
    r"(^next$|^>$|^>>$|^›$|^»$|next\s*page|next\s*›|load\s*more)",
    re.IGNORECASE,
)

# Single source of truth for numbered-pagination URLs: the capture groups yield
# the page number, and the same pattern is used both to *detect* a paginated URL
# and to *extract* its number — so the two can't drift apart (which was the bug
# behind #77, where detection matched offset=/start=//p/ but extraction didn't).
_PAGE_NUMBER = re.compile(
    r"[?&](?:page|p|pg|offset|start)=(\d+)|/(?:page|p)/(\d+)",
    re.IGNORECASE,
)


def find_next_page_url(soup: BeautifulSoup, current_url: str) -> str | None:
    """Detect the next-page URL from the current page's HTML.

    Looks for:
    1. ``<link rel="next">`` in ``<head>``
    2. ``<a>`` tags whose text matches "next", ">", ">>", etc.
    3. ``<a>`` tags whose class/aria-label suggest pagination

    Returns the absolute URL of the next page, or ``None`` if not found.
    """
    # 1. <link rel="next">
    link_next = soup.find("link", rel="next")
    if link_next and isinstance(link_next, Tag):
        href = link_next.get("href")
        if href:
            return urljoin(current_url, str(href))

    # 2. <a> with "next" text or aria-label
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        aria = str(a.get("aria-label", ""))
        classes = " ".join(a.get("class", []))

        if _NEXT_PATTERNS.search(text) or _NEXT_PATTERNS.search(aria):
            return urljoin(current_url, str(a["href"]))

        if "next" in classes.lower() and _PAGE_NUMBER.search(str(a["href"])):
            return urljoin(current_url, str(a["href"]))

    # 3. Look for numbered pagination links and pick the next number
    page_links = _find_page_number_links(soup, current_url)
    if page_links:
        current_num = _extract_page_number(current_url)
        if current_num is not None:
            step = _page_step(current_url, page_links)
            if step is None:
                return None
            target = current_num + step
            for num, url in page_links:
                if num == target:
                    return url

    return None


def _page_step(current_url: str,
               page_links: list[tuple[int, str]]) -> int | None:
    """Increment between numbered pages.

    For offset=/start= URLs the step is the page size, inferred from the gaps
    between the page-link values (issue #151: +1 is almost always wrong there).
    For page/p URLs the step is always 1.
    """
    if _is_offset_style(current_url):
        values = sorted({num for num, _ in page_links})
        steps = {b - a for a, b in zip(values, values[1:]) if b > a}
        if steps:
            return min(steps)
        return None
    return 1


def _is_offset_style(url: str) -> bool:
    """True if the URL's numbered parameter is offset=/start=."""
    match = _PAGE_NUMBER.search(url)
    if not match or match.group(1) is None:
        return False
    key = url[match.start():match.start(1)].lstrip("?&").rstrip("=").lower()
    return key in ("offset", "start")


def _find_page_number_links(soup: BeautifulSoup, base_url: str) -> list[tuple[int, str]]:
    """Find pagination links that contain page numbers."""
    results: list[tuple[int, str]] = []
    for a in soup.find_all("a", href=True):
        href = str(a["href"])
        if not _PAGE_NUMBER.search(href):
            continue
        num = _extract_page_number(href)
        if num is not None:
            results.append((num, urljoin(base_url, href)))
    return results


def _extract_page_number(url: str) -> int | None:
    """Extract a page number from a URL, or None if it isn't paginated."""
    match = _PAGE_NUMBER.search(url)
    if not match:
        return None
    return int(match.group(1) or match.group(2))
