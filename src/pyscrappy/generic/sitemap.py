"""Sitemap parsing and discovery.

The other half of "crawl everything": pagination follows next-page links, while a
sitemap enumerates a site's URLs directly and reliably. This module is pure
parsing — no network. :class:`~pyscrappy.generic.scraper.GenericScraper` wires it
to the HTTP client (fetching, robots, rate-limit, cache) via ``sitemap_urls`` and
``scrape_sitemap``.

Handles both sitemap flavors (https://www.sitemaps.org/protocol.html):

- ``<urlset>`` — a leaf sitemap listing page ``<loc>`` URLs.
- ``<sitemapindex>`` — points to child sitemaps, each its own ``<loc>``.

Parsing is namespace-agnostic (sitemaps declare the sitemaps.org namespace, but
we match on the local tag name so a missing/odd namespace still works) and
forgiving: a malformed document yields empty lists rather than raising.
"""

from __future__ import annotations

import gzip
import re
from xml.etree import ElementTree as ET

_GZIP_MAGIC = b"\x1f\x8b"


def maybe_gunzip(data: bytes) -> bytes:
    """Decompress ``data`` if it is gzip (``.xml.gz`` sitemaps are common).

    Detected by the gzip magic bytes rather than the URL suffix, since servers
    serve gzipped sitemaps under plain ``.xml`` URLs too. Returns the input
    unchanged if it isn't gzip or can't be decompressed."""
    if data[:2] == _GZIP_MAGIC:
        try:
            return gzip.decompress(data)
        except (OSError, EOFError):
            return data
    return data


def _local(tag: str) -> str:
    """Local tag name without its XML namespace ('{ns}loc' -> 'loc')."""
    return tag.rsplit("}", 1)[-1].lower()


def parse_sitemap(data: bytes) -> tuple[list[str], list[str]]:
    """Parse sitemap XML into ``(page_urls, child_sitemap_urls)``.

    - A ``<urlset>`` yields its ``<url><loc>`` values as ``page_urls``.
    - A ``<sitemapindex>`` yields its ``<sitemap><loc>`` values as
      ``child_sitemap_urls`` (the caller fetches those in turn).

    Robust to gzip input and to a missing/odd namespace. A parse error returns
    ``([], [])`` rather than raising, so one bad sitemap can't abort a crawl.
    """
    data = maybe_gunzip(data)
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return [], []

    root_tag = _local(root.tag)
    page_urls: list[str] = []
    child_sitemaps: list[str] = []

    if root_tag == "sitemapindex":
        for loc in root.iter():
            if _local(loc.tag) == "loc" and loc.text:
                child_sitemaps.append(loc.text.strip())
    else:
        # Treat anything else as a urlset (leaf). <urlset> is the common case;
        # being lenient here means a non-standard root still yields its <loc>s.
        for loc in root.iter():
            if _local(loc.tag) == "loc" and loc.text:
                page_urls.append(loc.text.strip())

    return page_urls, child_sitemaps


_SITEMAP_DIRECTIVE = re.compile(r"^\s*sitemap\s*:\s*(\S+)", re.IGNORECASE | re.MULTILINE)


def sitemaps_from_robots(robots_txt: str) -> list[str]:
    """Extract ``Sitemap:`` directive URLs from robots.txt content.

    robots.txt may list one or more ``Sitemap: <absolute-url>`` lines; these are
    the site's own declaration of where its sitemaps live and are preferred over
    guessing ``/sitemap.xml``."""
    return [m.group(1).strip() for m in _SITEMAP_DIRECTIVE.finditer(robots_txt or "")]
