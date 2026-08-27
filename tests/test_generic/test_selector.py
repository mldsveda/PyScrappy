"""Tests for the chainable Selector parser."""

from pyscrappy import Selector
from pyscrappy.generic.adaptive_store import AdaptiveStore

_HTML = """
<html><body>
  <div class="list">
    <div class="product featured" id="p1">
      <h2 class="title">Alpha</h2>
      <span class="price">$10</span>
      <a href="/a">buy</a>
    </div>
    <div class="product" id="p2">
      <h2 class="title">Beta</h2>
      <span class="price">$20</span>
      <a href="/b">buy</a>
    </div>
    <section class="other"><p>unrelated</p></section>
  </div>
  <button>Add to cart</button>
</body></html>
"""


def _page():
    return Selector(_HTML)


class TestCss:
    def test_css_returns_elements(self):
        products = _page().css(".product")
        assert len(products) == 2
        assert products[0].attrs["id"] == "p1"

    def test_css_text_pseudo_get_and_getall(self):
        page = _page()
        assert page.css(".title::text").get() == "Alpha"
        assert page.css(".title::text").getall() == ["Alpha", "Beta"]

    def test_css_attr_pseudo(self):
        assert _page().css("a::attr(href)").getall() == ["/a", "/b"]

    def test_css_attr_pseudo_normalizes_class(self):
        assert Selector('<a class="x y">link</a>').css("a::attr(class)").get() == "x y"

    def test_css_attr_pseudo_normalizes_rel(self):
        html = '<a rel="nofollow noopener">link</a>'
        assert Selector(html).css("a::attr(rel)").get() == "nofollow noopener"

    def test_css_attr_pseudo_preserves_scalar_attribute(self):
        assert Selector('<a href="/p">link</a>').css("a::attr(href)").get() == "/p"

    def test_css_attr_pseudo_getall_normalizes_multi_valued_attributes(self):
        html = '<a class="x y">one</a><a class="m n">two</a>'
        assert Selector(html).css("a::attr(class)").getall() == ["x y", "m n"]

    def test_css_attr_missing_attribute_uses_default(self):
        assert Selector("<a>x</a>").css("a::attr(href)").get("MISSING") == "MISSING"

    def test_css_attr_getall_skips_missing_attributes(self):
        html = "<a href='/present'>yes</a><a>missing</a>"
        assert Selector(html).css("a::attr(href)").getall() == ["/present"]

    def test_css_chaining(self):
        first = _page().css(".product")[0]
        assert first.css(".price::text").get() == "$10"

    def test_text_helper(self):
        assert _page().css(".title").text() == ["Alpha", "Beta"]


class TestXpath:
    def test_xpath_elements(self):
        assert len(_page().xpath('//div[@class="product"]')) >= 1

    def test_xpath_text(self):
        vals = _page().xpath('//span[@class="price"]/text()').getall()
        assert vals == ["$10", "$20"]

    def test_xpath_attr(self):
        assert _page().xpath("//a/@href").getall() == ["/a", "/b"]

    def test_xpath_scalar_count(self):
        # count(...) returns a float scalar from lxml; it must come back as a
        # string result rather than crashing (#136).
        assert _page().xpath("count(//div[contains(@class,'product')])").get() == "2.0"

    def test_xpath_scalar_boolean(self):
        assert _page().xpath("boolean(//div[contains(@class,'product')])").get() == "True"


class TestFindAll:
    def test_find_all_by_tag(self):
        assert len(_page().find_all("a")) == 2

    def test_find_all_by_class(self):
        titles = _page().find_all("h2", class_="title")
        assert [t.text() for t in titles] == ["Alpha", "Beta"]

    def test_find_all_by_attr(self):
        found = _page().find_all("div", id="p2")
        assert len(found) == 1
        assert found[0].attrs["id"] == "p2"


class TestFindByText:
    def test_substring_match(self):
        hits = _page().find_by_text("Add to cart")
        assert any(h.tag == "button" for h in hits)

    def test_case_insensitive_default(self):
        assert len(_page().find_by_text("alpha")) >= 1

    def test_exact_match(self):
        # "Alpha" exact matches the h2; a substring like "Alph" would not.
        assert len(_page().find_by_text("Alph", exact=True)) == 0
        assert len(_page().find_by_text("Alpha", tag="h2", exact=True)) == 1

    def test_tag_filter(self):
        assert all(h.tag == "h2" for h in _page().find_by_text("Beta", tag="h2"))


class TestFindSimilar:
    def test_finds_siblings_with_shared_class(self):
        first = _page().css(".product")[0]  # id=p1, classes product+featured
        similar = first.find_similar()
        ids = {s.attrs.get("id") for s in similar}
        assert "p2" in ids  # the other .product
        assert first.attrs["id"] not in ids  # excludes itself

    def test_does_not_match_unrelated_siblings(self):
        first = _page().css(".product")[0]
        similar = first.find_similar()
        # the <section class="other"> is a different tag, so never similar
        assert all(s.tag == "div" for s in similar)

    def test_limit(self):
        first = _page().css(".product")[0]
        assert len(first.find_similar(limit=1)) == 1


def test_selector_accepts_prebuilt_html_string():
    # The documented "use the parser directly" entry point.
    page = Selector("<div><p class='x'>hi</p></div>")
    assert page.css(".x::text").get() == "hi"


def test_derived_selectors_preserve_url_and_adaptive_store(tmp_path):
    store = AdaptiveStore(tmp_path / "adaptive.json")
    page = Selector(_HTML, url="https://shop.example.com/products", adaptive_store=store)
    product = page.css(".product")[0]
    derived = [
        product,
        page.xpath("//div[@id='p1']")[0],
        page.find_all("div", id="p1")[0],
        page.find_by_text("Alpha", tag="h2", exact=True)[0],
        product.find_similar()[0],
        product.parent,
    ]

    for child in derived:
        assert child is not None
        assert child._url == "https://shop.example.com/products"
        assert child._store is store
        assert child._namespace() == "shop.example.com"
