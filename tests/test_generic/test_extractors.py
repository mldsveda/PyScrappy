"""Tests for pyscrappy.generic.extractors."""

from bs4 import BeautifulSoup

from pyscrappy.generic.extractors import (
    ImageExtractor,
    LinkExtractor,
    MetadataExtractor,
    TableExtractor,
    TextExtractor,
)


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


class TestMetadataExtractor:
    def setup_method(self):
        self.extractor = MetadataExtractor()

    def test_extract_title(self):
        soup = _soup("<html><head><title>Test Page</title></head></html>")
        result = self.extractor.extract(soup)
        assert result["title"] == "Test Page"

    def test_extract_description(self):
        soup = _soup('<html><head><meta name="description" content="A test page"></head></html>')
        result = self.extractor.extract(soup)
        assert result["description"] == "A test page"

    def test_extract_author(self):
        soup = _soup('<html><head><meta name="author" content="John Doe"></head></html>')
        result = self.extractor.extract(soup)
        assert result["author"] == "John Doe"

    def test_extract_keywords(self):
        soup = _soup(
            '<html><head><meta name="keywords" content="python, scraping, web"></head></html>'
        )
        result = self.extractor.extract(soup)
        assert result["keywords"] == ["python", "scraping", "web"]

    def test_extract_keywords_ignores_empty_entries(self):
        soup = _soup('<html><head><meta name="keywords" content="python, , web,,"></head></html>')
        result = self.extractor.extract(soup)
        assert result["keywords"] == ["python", "web"]

    def test_extract_og_tags(self):
        soup = _soup(
            "<html><head>"
            '<meta property="og:title" content="OG Title">'
            '<meta property="og:image" content="https://img.com/pic.jpg">'
            "</head></html>"
        )
        result = self.extractor.extract(soup)
        assert result["og"]["title"] == "OG Title"
        assert result["og"]["image"] == "https://img.com/pic.jpg"

    def test_extract_twitter_card(self):
        soup = _soup(
            '<html><head><meta name="twitter:card" content="summary_large_image"></head></html>'
        )
        result = self.extractor.extract(soup)
        assert result["twitter_card"]["card"] == "summary_large_image"

    def test_extract_canonical_url(self):
        soup = _soup(
            '<html><head><link rel="canonical" href="https://example.com/page"></head></html>'
        )
        result = self.extractor.extract(soup)
        assert result["canonical_url"] == "https://example.com/page"

    def test_extract_language(self):
        soup = _soup('<html lang="en"><head></head></html>')
        result = self.extractor.extract(soup)
        assert result["language"] == "en"

    def test_empty_page(self):
        soup = _soup("<html><head></head><body></body></html>")
        result = self.extractor.extract(soup)
        assert "title" not in result
        assert "description" not in result

    def test_ignores_meta_without_content(self):
        soup = _soup('<html><head><meta name="description"></head></html>')
        result = self.extractor.extract(soup)
        assert "description" not in result


class TestTextExtractor:
    def setup_method(self):
        self.extractor = TextExtractor()

    def test_extract_paragraphs(self):
        soup = _soup(
            "<html><body>"
            "<p>This is a paragraph with enough text to pass the filter threshold easily.</p>"
            "<p>Another paragraph that is also long enough to be captured by the extractor.</p>"
            "</body></html>"
        )
        result = self.extractor.extract(soup)
        assert len(result["paragraphs"]) == 2
        assert result["word_count"] > 0

    def test_extract_from_article_tag(self):
        soup = _soup(
            "<html><body>"
            "<nav>Navigation links that should be removed from output</nav>"
            "<article>"
            "<p>This is the main article content that should be extracted properly.</p>"
            "</article>"
            "</body></html>"
        )
        result = self.extractor.extract(soup)
        assert len(result["paragraphs"]) >= 1
        assert "main article content" in result["text"]

    def test_extract_headings(self):
        soup = _soup(
            "<html><body><h1>Main Title</h1><h2>Section One</h2><h3>Subsection</h3></body></html>"
        )
        result = self.extractor.extract(soup)
        assert len(result["headings"]) == 3
        assert result["headings"][0] == {"level": "h1", "text": "Main Title"}
        assert result["headings"][1] == {"level": "h2", "text": "Section One"}

    def test_noise_removal(self):
        soup = _soup(
            "<html><body>"
            "<script>var x = 1;</script>"
            "<style>.a { color: red; }</style>"
            "<nav>Nav content</nav>"
            "<footer>Footer content</footer>"
            "<p>This is the actual content paragraph that matters for extraction.</p>"
            "</body></html>"
        )
        result = self.extractor.extract(soup)
        assert "var x = 1" not in result["text"]
        assert "color: red" not in result["text"]

    def test_empty_page_returns_empty(self):
        soup = _soup("<html><body></body></html>")
        result = self.extractor.extract(soup)
        assert result["paragraphs"] == []
        assert result["word_count"] == 0

    def test_removes_noise_classes(self):
        soup = _soup(
            "<html><body>"
            '<div class="sidebar">Sidebar content</div>'
            '<div class="ad-banner">Ad content</div>'
            "<p>This is the real content paragraph of the page that should remain.</p>"
            "</body></html>"
        )
        result = self.extractor.extract(soup)
        assert "Sidebar content" not in result["text"]

    def test_word_count(self):
        soup = _soup(
            "<html><body>"
            "<p>One two three four five six seven eight nine ten and some more words.</p>"
            "</body></html>"
        )
        result = self.extractor.extract(soup)
        assert result["word_count"] > 0


class TestLinkExtractor:
    def setup_method(self):
        self.extractor = LinkExtractor()

    def test_extract_links(self):
        soup = _soup(
            "<html><body>"
            '<a href="https://example.com/page1">Page 1</a>'
            '<a href="/page2">Page 2</a>'
            "</body></html>"
        )
        result = self.extractor.extract(soup, "https://example.com")
        assert len(result) == 2
        assert result[0]["url"] == "https://example.com/page1"
        assert result[0]["text"] == "Page 1"
        assert result[1]["url"] == "https://example.com/page2"

    def test_deduplication(self):
        soup = _soup(
            "<html><body>"
            '<a href="https://example.com/page">Link 1</a>'
            '<a href="https://example.com/page">Link 2</a>'
            "</body></html>"
        )
        result = self.extractor.extract(soup, "https://example.com")
        assert len(result) == 1

    def test_skips_javascript_mailto_tel_hash(self):
        soup = _soup(
            "<html><body>"
            '<a href="javascript:void(0)">JS</a>'
            '<a href="mailto:test@test.com">Email</a>'
            '<a href="tel:+1234567890">Phone</a>'
            '<a href="#">Top</a>'
            '<a href="https://real.com">Real</a>'
            "</body></html>"
        )
        result = self.extractor.extract(soup)
        assert len(result) == 1
        assert result[0]["url"] == "https://real.com"

    def test_extracts_rel(self):
        soup = _soup(
            "<html><body>"
            '<a href="https://external.com" rel="nofollow noopener">External</a>'
            "</body></html>"
        )
        result = self.extractor.extract(soup)
        assert result[0]["rel"] == "nofollow noopener"

    def test_empty_href_skipped(self):
        soup = _soup('<html><body><a href="">Empty</a></body></html>')
        result = self.extractor.extract(soup)
        assert len(result) == 0

    def test_relative_urls_resolved(self):
        soup = _soup('<html><body><a href="/relative/path">Link</a></body></html>')
        result = self.extractor.extract(soup, "https://base.com")
        assert result[0]["url"] == "https://base.com/relative/path"


class TestImageExtractor:
    def setup_method(self):
        self.extractor = ImageExtractor()

    def test_extract_images(self):
        soup = _soup(
            "<html><body>"
            '<img src="https://img.com/pic.jpg" alt="A picture" width="100" height="200">'
            "</body></html>"
        )
        result = self.extractor.extract(soup)
        assert len(result) == 1
        assert result[0]["url"] == "https://img.com/pic.jpg"
        assert result[0]["alt"] == "A picture"
        assert result[0]["width"] == "100"
        assert result[0]["height"] == "200"

    def test_lazy_loaded_images(self):
        soup = _soup(
            '<html><body><img data-src="https://img.com/lazy.jpg" alt="Lazy"></body></html>'
        )
        result = self.extractor.extract(soup)
        assert len(result) == 1
        assert result[0]["url"] == "https://img.com/lazy.jpg"

    def test_data_lazy_src(self):
        soup = _soup(
            '<html><body><img data-lazy-src="https://img.com/lazy2.jpg" alt="Lazy2"></body></html>'
        )
        result = self.extractor.extract(soup)
        assert result[0]["url"] == "https://img.com/lazy2.jpg"

    def test_skips_images_without_src(self):
        soup = _soup('<html><body><img alt="No source"></body></html>')
        result = self.extractor.extract(soup)
        assert len(result) == 0

    def test_relative_image_url_resolved(self):
        soup = _soup('<html><body><img src="/images/pic.jpg"></body></html>')
        result = self.extractor.extract(soup, "https://example.com")
        assert result[0]["url"] == "https://example.com/images/pic.jpg"

    def test_missing_attributes_default_empty(self):
        soup = _soup('<html><body><img src="https://img.com/x.jpg"></body></html>')
        result = self.extractor.extract(soup)
        assert result[0]["alt"] == ""
        assert result[0]["width"] == ""
        assert result[0]["height"] == ""

    def test_non_string_attributes(self):
        # BeautifulSoup will parse 'class' or other multi-valued attributes as a list.
        # Although alt/width/height are not officially multi-valued, a malformed HTML
        # or specific parser might return lists. We test by artificially setting a list.
        soup = _soup('<html><body><img src="https://img.com/x.jpg" alt="a b"></body></html>')
        img = soup.find("img")
        img["alt"] = ["a", "b"]
        img["width"] = ["100", "200"]
        img["height"] = ["300", "400"]
        result = self.extractor.extract(soup)
        assert result[0]["alt"] == str(["a", "b"])
        assert result[0]["width"] == str(["100", "200"])
        assert result[0]["height"] == str(["300", "400"])


class TestTableExtractor:
    def setup_method(self):
        self.extractor = TableExtractor()

    def test_extract_table(self):
        soup = _soup(
            "<html><body><table>"
            "<tr><th>Name</th><th>Age</th></tr>"
            "<tr><td>Alice</td><td>30</td></tr>"
            "<tr><td>Bob</td><td>25</td></tr>"
            "</table></body></html>"
        )
        result = self.extractor.extract(soup)
        assert len(result) == 1
        assert len(result[0]) == 2
        assert result[0][0] == {"Name": "Alice", "Age": "30"}
        assert result[0][1] == {"Name": "Bob", "Age": "25"}

    def test_multiple_tables(self):
        soup = _soup(
            "<html><body>"
            "<table><tr><th>A</th></tr><tr><td>1</td></tr></table>"
            "<table><tr><th>B</th></tr><tr><td>2</td></tr></table>"
            "</body></html>"
        )
        result = self.extractor.extract(soup)
        assert len(result) == 2

    def test_keeps_short_rows_padding_missing_cells(self):
        # A row with fewer cells than the header is kept, not dropped: the
        # missing trailing columns become "" so the row still appears. #105
        soup = _soup(
            "<html><body><table>"
            "<tr><th>A</th><th>B</th></tr>"
            "<tr><td>1</td></tr>"
            "<tr><td>2</td><td>3</td></tr>"
            "</table></body></html>"
        )
        result = self.extractor.extract(soup)
        assert len(result) == 1
        assert len(result[0]) == 2
        assert result[0][0] == {"A": "1", "B": ""}
        assert result[0][1] == {"A": "2", "B": "3"}

    def test_keeps_long_rows_under_positional_keys(self):
        # A row with more cells than the header keeps the surplus values under
        # positional keys instead of silently discarding them. #105
        soup = _soup(
            "<html><body><table>"
            "<tr><th>A</th><th>B</th></tr>"
            "<tr><td>1</td><td>2</td><td>extra</td></tr>"
            "</table></body></html>"
        )
        result = self.extractor.extract(soup)
        assert len(result) == 1
        assert result[0][0] == {"A": "1", "B": "2", "column_3": "extra"}

    def test_empty_table_skipped(self):
        soup = _soup("<html><body><table></table></body></html>")
        result = self.extractor.extract(soup)
        assert result == []

    def test_table_with_no_data_rows(self):
        soup = _soup("<html><body><table><tr><th>Header</th></tr></table></body></html>")
        result = self.extractor.extract(soup)
        assert result == []

    def test_headers_from_td_in_first_row(self):
        soup = _soup(
            "<html><body><table>"
            "<tr><td>Col1</td><td>Col2</td></tr>"
            "<tr><td>A</td><td>B</td></tr>"
            "</table></body></html>"
        )
        result = self.extractor.extract(soup)
        assert len(result) == 1
        assert result[0][0] == {"Col1": "A", "Col2": "B"}
