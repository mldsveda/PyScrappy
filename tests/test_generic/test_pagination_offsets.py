"""Regression tests for offset/start pagination (issue #151)."""

from bs4 import BeautifulSoup

from pyscrappy.generic.pagination import (
    _extract_page_number,
    _page_step,
    find_next_page_url,
)


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def _links(values, param="offset"):
    return _soup(
        "".join('<a href="/list?%s=%d">p%d</a>' % (param, v, i) for i, v in enumerate(values))
    )


def test_offset_pagination_advances_by_inferred_page_size():
    # links at 0/20/40/60 -> step 20; current offset=20 -> next is 40
    soup = _links([0, 20, 40, 60])
    result = find_next_page_url(soup, "https://x.com/list?offset=20")
    assert result == "https://x.com/list?offset=40"


def test_start_pagination_advances_by_inferred_page_size():
    soup = _links([0, 50, 100], param="start")
    result = find_next_page_url(soup, "https://x.com/list?start=0")
    assert result == "https://x.com/list?start=50"


def test_offset_step_is_inferred_not_hardcoded():
    assert _page_step("https://x.com/list?offset=20", [(20, ""), (45, ""), (70, "")]) == 25


def test_page_param_still_advances_by_one():
    soup = _soup('<a href="?page=2">2</a><a href="?page=3">3</a>')
    result = find_next_page_url(soup, "https://x.com/list?page=1")
    assert result == "https://x.com/list?page=2"


def test_offset_without_link_steps_returns_none():
    soup = _links([20])
    assert find_next_page_url(soup, "https://x.com/list?offset=20") is None


def test_extract_offset_value():
    assert _extract_page_number("https://x.com/list?offset=20") == 20
