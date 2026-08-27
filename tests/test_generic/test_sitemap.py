"""Tests for sitemap parsing (pure) and GenericScraper sitemap crawling (#160)."""

import gzip
from unittest.mock import MagicMock

from pyscrappy import GenericScraper
from pyscrappy.generic.sitemap import (
    maybe_gunzip,
    parse_sitemap,
    sitemaps_from_robots,
)

_NS = 'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'


def _urlset(*urls):
    body = "".join(f"<url><loc>{u}</loc></url>" for u in urls)
    return f"<urlset {_NS}>{body}</urlset>".encode()


def _index(*sitemaps):
    body = "".join(f"<sitemap><loc>{s}</loc></sitemap>" for s in sitemaps)
    return f"<sitemapindex {_NS}>{body}</sitemapindex>".encode()


# -- pure parsing --


def test_parse_urlset():
    pages, children = parse_sitemap(_urlset("https://x.com/a", "https://x.com/b"))
    assert pages == ["https://x.com/a", "https://x.com/b"]
    assert children == []


def test_parse_sitemapindex():
    pages, children = parse_sitemap(_index("https://x.com/s1.xml", "https://x.com/s2.xml"))
    assert pages == []
    assert children == ["https://x.com/s1.xml", "https://x.com/s2.xml"]


def test_parse_gzip_sitemap():
    pages, _ = parse_sitemap(gzip.compress(_urlset("https://x.com/a")))
    assert pages == ["https://x.com/a"]


def test_maybe_gunzip_passthrough_for_plain_bytes():
    assert maybe_gunzip(b"<xml/>") == b"<xml/>"


def test_parse_garbage_returns_empty():
    assert parse_sitemap(b"<<not xml") == ([], [])
    assert parse_sitemap(b"") == ([], [])


def test_parse_ignores_namespace():
    # No namespace declared at all — local-name matching still finds <loc>.
    pages, _ = parse_sitemap(b"<urlset><url><loc>https://x.com/a</loc></url></urlset>")
    assert pages == ["https://x.com/a"]


def test_parse_excludes_extension_loc():
    # image:/video: extension namespaces nest their own <loc> (local name "loc")
    # inside a <url>; only the <url>'s direct-child <loc> is a page URL.
    ns = 'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'
    img = 'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"'
    xml = (
        f"<urlset {ns} {img}>"
        "<url><loc>https://x.com/page</loc>"
        "<image:image><image:loc>https://x.com/pic.jpg</image:loc></image:image>"
        "</url></urlset>"
    ).encode()
    pages, _ = parse_sitemap(xml)
    assert pages == ["https://x.com/page"]  # image URL excluded


def test_sitemaps_from_robots():
    txt = "User-agent: *\nSitemap: https://x.com/sitemap.xml\nSitemap: https://x.com/news.xml\n"
    assert sitemaps_from_robots(txt) == ["https://x.com/sitemap.xml", "https://x.com/news.xml"]
    assert sitemaps_from_robots("") == []


# -- GenericScraper.sitemap_urls --


def _scraper_with_responses(mapping, robots_txt=None, robots_raises=False):
    """A GenericScraper whose http.get returns bodies by URL substring. A missing
    URL raises (mirroring HttpClient.get's non-2xx behavior), which sitemap_urls
    treats as 'not there' and skips."""
    gs = GenericScraper()
    http = MagicMock()

    def get(url, **kwargs):
        resp = MagicMock()
        if "robots" in url:
            if robots_raises:
                raise RuntimeError("no robots")
            body = robots_txt or ""
            resp.text = body
            resp.content = body.encode()
            return resp
        for frag, body in mapping.items():
            if frag in url:
                resp.text = body.decode() if isinstance(body, bytes) else body
                resp.content = body if isinstance(body, bytes) else body.encode()
                return resp
        raise RuntimeError(f"404 {url}")  # unknown URL -> get() would raise

    http.get = get
    gs._http = http
    return gs


def test_sitemap_urls_recurses_index_via_robots():
    gs = _scraper_with_responses(
        {
            "sitemap_index": _index("https://x.com/s1.xml"),
            "s1.xml": _urlset("https://x.com/p0", "https://x.com/p1"),
        },
        robots_txt="Sitemap: https://x.com/sitemap_index.xml\n",
    )
    assert gs.sitemap_urls("https://x.com/page") == ["https://x.com/p0", "https://x.com/p1"]


def test_sitemap_urls_max_urls_caps():
    gs = _scraper_with_responses(
        {"sitemap.xml": _urlset(*[f"https://x.com/p{i}" for i in range(10)])},
        robots_txt="Sitemap: https://x.com/sitemap.xml\n",
    )
    assert gs.sitemap_urls("https://x.com/p", max_urls=3) == [
        "https://x.com/p0",
        "https://x.com/p1",
        "https://x.com/p2",
    ]


def test_sitemap_urls_falls_back_to_sitemap_xml_without_robots():
    gs = _scraper_with_responses(
        {"sitemap.xml": _urlset("https://x.com/a")},
        robots_raises=True,
    )
    assert gs.sitemap_urls("https://x.com/p") == ["https://x.com/a"]


def test_sitemap_urls_dedupes():
    gs = _scraper_with_responses(
        {"sitemap.xml": _urlset("https://x.com/a", "https://x.com/a", "https://x.com/b")},
        robots_txt="Sitemap: https://x.com/sitemap.xml\n",
    )
    assert gs.sitemap_urls("https://x.com/p") == ["https://x.com/a", "https://x.com/b"]


def test_sitemap_urls_index_only_recurses_one_level():
    # A child sitemap that is itself an index must NOT be descended into further.
    gs = _scraper_with_responses(
        {
            "top.xml": _index("https://x.com/mid.xml"),
            "mid.xml": _index("https://x.com/leaf.xml"),  # child index — not followed
            "leaf.xml": _urlset("https://x.com/deep"),
        },
        robots_txt="Sitemap: https://x.com/top.xml\n",
    )
    # top -> mid (an index, treated as a child; its children are not followed),
    # so no page URLs are reached.
    assert gs.sitemap_urls("https://x.com/p") == []


def test_scrape_sitemap_merges_results(monkeypatch):
    gs = _scraper_with_responses(
        {"sitemap.xml": _urlset("https://x.com/a", "https://x.com/b")},
        robots_txt="Sitemap: https://x.com/sitemap.xml\n",
    )

    # Stub scrape_all to avoid real page fetches; return one item per URL.
    import pyscrappy.generic.scraper as scraper_mod
    from pyscrappy.core.models import ScrapeMetadata, ScrapeResult

    def fake_scrape_all(funcs, max_workers=8):
        return [
            ScrapeResult(data=[{"i": n}], metadata=ScrapeMetadata()) for n, _ in enumerate(funcs)
        ]

    monkeypatch.setattr(scraper_mod, "scrape_all", fake_scrape_all, raising=False)
    # scrape_all is imported inside the method, so patch the source module too.
    monkeypatch.setattr("pyscrappy.concurrent.scrape_all", fake_scrape_all)

    result = gs.scrape_sitemap("https://x.com/p", max_urls=10)
    assert len(result.data) == 2
    assert result.metadata.total_pages == 2
    assert result.metadata.scraper == "generic:sitemap"


def test_scrape_sitemap_no_urls_returns_error():
    gs = _scraper_with_responses({}, robots_raises=True)
    result = gs.scrape_sitemap("https://x.com/p")
    assert result.data == []
    assert result.errors and "no sitemap URLs" in result.errors[0].message
