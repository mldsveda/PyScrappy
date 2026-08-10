"""A chainable HTML parser object, in the spirit of Scrapy/BeautifulSoup.

Most of PyScrappy returns structured dicts. ``Selector`` is the escape hatch for
when you want to *navigate* HTML directly: select by CSS or XPath, filter
BeautifulSoup-style, search by text, and locate elements structurally similar to
one you already found.

Usage::

    from pyscrappy import Selector

    page = Selector(html)
    titles = page.css(".title").text()            # list[str]
    first = page.css(".product")[0]
    price = first.css(".price::text").get()       # supports the ::text pseudo-element
    rows = page.find_all("a", class_="nav")       # BS4-style
    hits = page.find_by_text("Add to cart")       # text search
    more = first.find_similar()                   # elements shaped like `first`
"""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup, Tag
from lxml import etree

# CSS with a trailing ``::text`` / ``::attr(name)`` pseudo-element, Scrapy-style.
_PSEUDO = re.compile(r"^(?P<sel>.*?)::(?P<kind>text|attr\((?P<attr>[^)]+)\))$", re.DOTALL)


class Selector:
    """A single HTML element (or a whole document) you can query and navigate."""

    def __init__(self, html: str | Tag, _parser: str = "lxml") -> None:
        if isinstance(html, Tag):
            self._node: Tag = html
        else:
            self._node = BeautifulSoup(html, _parser)
        self._parser = _parser

    # -- basic access --
    @property
    def tag(self) -> str | None:
        """This element's tag name (None for a whole-document root)."""
        return getattr(self._node, "name", None)

    @property
    def attrs(self) -> dict[str, Any]:
        """This element's attributes."""
        return dict(getattr(self._node, "attrs", {}))

    def text(self, strip: bool = True) -> str:
        """This element's text content."""
        return self._node.get_text(strip=strip)

    def html(self) -> str:
        """This element's outer HTML."""
        return str(self._node)

    # -- selection --
    def css(self, selector: str) -> SelectorList:
        """Select descendants by CSS. Supports a trailing ``::text`` or
        ``::attr(name)`` pseudo-element (the values are read via ``.get()`` /
        ``.getall()`` on the returned list)."""
        m = _PSEUDO.match(selector)
        base, pseudo, attr = selector, None, None
        if m:
            base = m.group("sel") or "*"
            pseudo = "text" if m.group("kind") == "text" else "attr"
            attr = m.group("attr")
        matches = self._node.select(base)
        return SelectorList(
            [Selector(el, self._parser) for el in matches], pseudo=pseudo, attr=attr
        )

    def xpath(self, path: str) -> SelectorList:
        """Select descendants by XPath (via lxml). Returns elements; text/attr
        XPath expressions (``.../text()``, ``.../@href``) yield string results."""
        root = etree.HTML(str(self._node))
        if root is None:
            return SelectorList([])
        results = root.xpath(path)
        selectors: list[Selector] = []
        strings: list[str] = []
        for r in results:
            if isinstance(r, str):
                strings.append(r)
            else:
                selectors.append(
                    Selector(BeautifulSoup(etree.tostring(r), self._parser), self._parser)
                )
        if strings:  # a text()/@attr XPath: expose the strings directly
            return SelectorList([], _strings=strings)
        return SelectorList(selectors)

    def find_all(
        self, name: str | list[str] | None = None, class_: str | None = None, **attrs: str
    ) -> SelectorList:
        """BeautifulSoup-style search: by tag name, ``class_``, and/or attributes."""
        kwargs: dict[str, Any] = dict(attrs)
        if class_ is not None:
            kwargs["class_"] = class_
        matches = self._node.find_all(name, **kwargs)
        return SelectorList([Selector(el, self._parser) for el in matches])

    def find_by_text(self, text: str, tag: str | None = None, exact: bool = False) -> SelectorList:
        """Find elements whose text contains ``text`` (or equals it, if ``exact``).
        Optionally restrict to a given ``tag``."""
        needle = text if exact else text.lower()

        def matches(el: Tag) -> bool:
            content = el.get_text(strip=True)
            return content == text if exact else needle in content.lower()

        found = [
            el for el in self._node.find_all(tag or True) if isinstance(el, Tag) and matches(el)
        ]
        return SelectorList([Selector(el, self._parser) for el in found])

    def find_similar(self, limit: int | None = None) -> SelectorList:
        """Find sibling-level elements structurally similar to this one: same tag
        and overlapping class set. Useful for pulling every card/row once you've
        located one (e.g. one product tile -> all product tiles)."""
        if not isinstance(self._node, Tag) or self._node.parent is None:
            return SelectorList([])
        my_tag = self._node.name
        my_classes = set(self._node.get("class") or [])
        similar: list[Selector] = []
        for sib in self._node.parent.find_all(my_tag, recursive=False):
            if sib is self._node:
                continue
            sib_classes = set(sib.get("class") or [])
            # Same tag, and (no classes to compare) or a shared class.
            if not my_classes or (my_classes & sib_classes):
                similar.append(Selector(sib, self._parser))
                if limit is not None and len(similar) >= limit:
                    break
        return SelectorList(similar)

    # -- navigation --
    @property
    def parent(self) -> Selector | None:
        p = getattr(self._node, "parent", None)
        return Selector(p, self._parser) if isinstance(p, Tag) else None

    def __repr__(self) -> str:
        return f"<Selector {self.tag or 'document'}>"


class SelectorList(list):
    """A list of :class:`Selector` results, with helpers to pull text/attrs.

    A CSS ``::text`` / ``::attr(...)`` pseudo-element (or a text/@attr XPath) sets
    the list up so ``.get()`` / ``.getall()`` return those string values instead
    of elements.
    """

    def __init__(
        self, items=(), *, pseudo: str | None = None, attr: str | None = None, _strings=None
    ):
        super().__init__(items)
        self._pseudo = pseudo
        self._attr = attr
        self._strings = _strings  # pre-computed string results (XPath text()/@attr)

    def _values(self) -> list[str]:
        if self._strings is not None:
            return list(self._strings)
        if self._pseudo == "text":
            return [s.text() for s in self]
        if self._pseudo == "attr":
            return [str(s.attrs.get(self._attr, "")) for s in self]
        return [s.html() for s in self]

    def get(self, default: str | None = None) -> str | None:
        """First result's value (text/attr/html per the selector), or ``default``."""
        values = self._values()
        return values[0] if values else default

    def getall(self) -> list[str]:
        """All results' values (text/attr/html per the selector)."""
        return self._values()

    def text(self, strip: bool = True) -> list[str]:
        """Text of each element in the list."""
        return [s.text(strip=strip) for s in self]
