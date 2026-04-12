"""Automatic pagination detection."""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag


_NEXT_PATTERNS = re.compile(
    r"(^next$|^>$|^>>$|^›$|^»$|next\s*page|next\s*›|load\s*more)",
    re.IGNORECASE,
)

_PAGE_URL_PATTERNS = re.compile(
    r"[?&](page|p|pg|offset|start)=\d+|/page/\d+|/p/\d+",
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

        if "next" in classes.lower() and _PAGE_URL_PATTERNS.search(str(a["href"])):
            return urljoin(current_url, str(a["href"]))

    # 3. Look for numbered pagination links and pick the next number
    page_links = _find_page_number_links(soup, current_url)
    if page_links:
        current_num = _extract_page_number(current_url)
        if current_num is not None:
            target = current_num + 1
            for num, url in page_links:
                if num == target:
                    return url

    return None


def _find_page_number_links(soup: BeautifulSoup, base_url: str) -> list[tuple[int, str]]:
    """Find pagination links that contain page numbers."""
    results: list[tuple[int, str]] = []
    for a in soup.find_all("a", href=True):
        href = str(a["href"])
        if not _PAGE_URL_PATTERNS.search(href):
            continue
        num = _extract_page_number(href)
        if num is not None:
            results.append((num, urljoin(base_url, href)))
    return results


def _extract_page_number(url: str) -> int | None:
    """Try to extract a page number from a URL."""
    match = re.search(r"[?&](?:page|p|pg)=(\d+)", url, re.IGNORECASE)
    if match:
        return int(match.group(1))
    match = re.search(r"/page/(\d+)", url, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None
