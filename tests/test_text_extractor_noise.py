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


def test_neutral_layout_labels_are_not_treated_as_noise():
    """Labels naming layout or content blocks must not delete their subtree."""
    html = (
        "<html><body>"
        '<div class="book-review"><p>Real review text long enough to be extracted here.</p></div>'
        '<div class="profile"><p>Profile block paragraph that must survive extraction.</p></div>'
        '<div class="gallery"><p>Gallery caption paragraph that must survive extraction.</p></div>'
        '<div class="accordion-content"><p>Accordion body paragraph that must survive.</p></div>'
        '<div class="search-results"><p>Search hit paragraph that must survive extraction.</p></div>'
        "</body></html>"
    )
    result = _extract(html)

    assert len(result["paragraphs"]) == 5
    for marker in (
        "Real review text",
        "Profile block",
        "Gallery caption",
        "Accordion body",
        "Search hit",
    ):
        assert marker in result["text"]


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
    for word in (
        "Navigation noise",
        "Sidebar noise",
        "Footer noise",
        "Comment noise",
        "Social noise",
    ):
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
        '<div class="cookie-banner"><p>Cookie notice paragraph that must never be extracted.</p></div>'
        '<div class="author-bio"><p>Author biography paragraph that must never be extracted.</p></div>'
        '<div class="content"><p>Surviving paragraph that must always be part of the result.</p></div>'
        "</body></html>"
    )
    result = _extract(html)

    assert len(result["paragraphs"]) == 1
    assert "Surviving paragraph" in result["text"]


def test_underscore_and_hyphen_separators_behave_the_same():
    html = (
        "<html><body>"
        '<div class="author_bio"><p>Author biography underscore paragraph that must go.</p></div>'
        '<div class="social_share"><p>Share widget underscore paragraph that must go.</p></div>'
        '<div id="sidebar_widget"><p>Sidebar underscore paragraph that must go.</p></div>'
        '<div class="content"><p>Underscore control paragraph that must always survive.</p></div>'
        "</body></html>"
    )
    result = _extract(html)

    assert len(result["paragraphs"]) == 1
    assert "Underscore control paragraph" in result["text"]


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


def test_cookie_content_labels_are_not_treated_as_noise():
    """A bare "cookie" word is content; only the cookie interface block is noise."""
    html = (
        "<html><body>"
        '<div class="post tag-cookies"><p>Cookie recipe paragraph that must survive extraction.</p></div>'
        '<div class="cookie-recipe"><p>Second recipe paragraph that must survive extraction.</p></div>'
        "</body></html>"
    )
    result = _extract(html)

    assert len(result["paragraphs"]) == 2
    assert "Cookie recipe paragraph" in result["text"]
    assert "Second recipe paragraph" in result["text"]


def test_explicit_cookie_interface_names_are_still_removed():
    html = (
        "<html><body>"
        '<div class="cookie-consent"><p>Consent paragraph that must never be extracted here.</p></div>'
        '<div class="content cookie-banner"><p>Banner paragraph that must never be extracted now.</p></div>'
        '<div class="content"><p>Surviving paragraph that must always be part of the result.</p></div>'
        "</body></html>"
    )
    result = _extract(html)

    assert len(result["paragraphs"]) == 1
    assert "Surviving paragraph" in result["text"]


def test_breadcrumb_blocks_are_removed():
    assert TextExtractor._is_noise("breadcrumb")
    assert TextExtractor._is_noise("content breadcrumb")
    html = (
        "<html><body>"
        '<div class="breadcrumb"><p>Breadcrumb trail paragraph that must never be extracted.</p></div>'
        '<div class="content"><p>Control paragraph that must always survive extraction.</p></div>'
        "</body></html>"
    )
    result = _extract(html)

    assert len(result["paragraphs"]) == 1
    assert "Control paragraph" in result["text"]
    assert "Breadcrumb trail paragraph" not in result["text"]
