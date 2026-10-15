"""Regression tests for noise removal in TextExtractor (#186)."""

from bs4 import BeautifulSoup

from pyscrappy.generic.extractors import TextExtractor


def _extract(html: str) -> dict:
    return TextExtractor().extract(BeautifulSoup(html, "html.parser"))


def test_ordinary_class_names_are_not_treated_as_noise():
    html = (
        "<html><body>"
        '<div class="gradient"><p>Real article paragraph one that must survive extraction.</p></div>'
        '<div class="download-guide"><p>Second real paragraph about downloads.</p></div>'
        '<div class="headline"><p>Third real paragraph under a headline block.</p></div>'
        "</body></html>"
    )
    result = _extract(html)

    assert len(result["paragraphs"]) == 3
    assert result["word_count"] > 0
    assert "headline block" in result["text"]


def test_noise_class_names_are_still_removed():
    html = (
        "<html><body>"
        '<div class="nav"><p>Navigation noise paragraph that should never be extracted here.</p></div>'
        '<div class="sidebar"><p>Sidebar noise paragraph that should never be extracted here.</p></div>'
        '<div class="footer"><p>Footer noise paragraph that should never be extracted here.</p></div>'
        '<div class="comment"><p>Comment noise paragraph that should never be extracted here.</p></div>'
        '<div class="social"><p>Social noise paragraph that should never be extracted here.</p></div>'
        '<div class="content"><p>Control paragraph that must always survive the extraction.</p></div>'
        "</body></html>"
    )
    result = _extract(html)

    assert len(result["paragraphs"]) == 1
    assert "Control paragraph" in result["text"]
    for word in ("Navigation noise", "Sidebar noise", "Footer noise", "Comment noise", "Social noise"):
        assert word not in result["text"]


def test_multi_class_element_with_noise_token_is_removed():
    html = (
        "<html><body>"
        '<div class="content"><p>Keep me: this paragraph belongs to the article body text.</p></div>'
        '<div class="content ad-banner"><p>Drop me: this paragraph lives inside an ad banner block.</p></div>'
        "</body></html>"
    )
    result = _extract(html)

    assert len(result["paragraphs"]) == 1
    assert "Keep me" in result["text"]
    assert "Drop me" not in result["text"]


def test_compound_noise_class_names_are_still_removed():
    html = (
        "<html><body>"
        '<div class="social-share"><p>Share widgets paragraph that should never be extracted.</p></div>'
        '<div class="comment-list"><p>Comment list paragraph that should never be extracted.</p></div>'
        '<div class="article"><p>Body paragraph that must survive the extraction of the page.</p></div>'
        "</body></html>"
    )
    result = _extract(html)

    assert len(result["paragraphs"]) == 1
    assert "Body paragraph" in result["text"]


def test_longer_noise_names_are_still_removed():
    html = (
        "<html><body>"
        '<div class="navigation"><p>Navigation block paragraph that must never be extracted.</p></div>'
        '<div class="advert"><p>Advertising block paragraph that must never be extracted.</p></div>'
        '<div class="newsletter"><p>Newsletter block paragraph that must never be extracted.</p></div>'
        '<div class="breadcrumb"><p>Breadcrumb block paragraph that must never be extracted.</p></div>'
        '<div class="cookie-banner"><p>Cookie banner paragraph that must never be extracted.</p></div>'
        '<div class="author-bio"><p>Author biography paragraph that must never be extracted.</p></div>'
        '<div class="content"><p>Surviving paragraph that must always be part of the result.</p></div>'
        "</body></html>"
    )
    result = _extract(html)

    assert len(result["paragraphs"]) == 1
    assert "Surviving paragraph" in result["text"]


def test_noise_ids_are_still_removed_without_anchored_false_negatives():
    html = (
        "<html><body>"
        '<div id="sidebar-widget"><p>Sidebar widget paragraph that must never be extracted.</p></div>'
        '<div id="main-content"><p>Main content paragraph that must survive extraction here.</p></div>'
        "</body></html>"
    )
    result = _extract(html)

    assert len(result["paragraphs"]) == 1
    assert "Main content paragraph" in result["text"]
