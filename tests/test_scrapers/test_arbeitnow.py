"""Tests for Arbeitnow using recorded JSON API responses."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from pyscrappy.scrapers.arbeitnow import ArbeitnowScraper


FIXTURES = Path(__file__).parents[1] / "fixtures" / "arbeitnow"


def _response(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _mock_sync(scraper: ArbeitnowScraper, *responses: str) -> MagicMock:
    http = MagicMock()
    http.get_html.side_effect = responses
    scraper._http = http
    return http


def _mock_async(scraper: ArbeitnowScraper, *responses: str) -> MagicMock:
    http = MagicMock()
    http.get_html = AsyncMock(side_effect=responses)
    scraper._async_http = http
    return http


def test_scrape_filters_jobs_and_normalizes_api_fields():
    scraper = ArbeitnowScraper()
    http = _mock_sync(scraper, _response("page1.json"))

    result = scraper.scrape(query="python", remote=True, job_type="contract")

    assert len(result.data) == 1
    job = result.data[0]
    assert job["title"] == "Python Remote Engineer"
    assert job["url"] == "https://jobs.example.test/python-remote-engineer"
    assert job["job_type"] == "Contract"
    assert job["created_at"] == "2026-01-03T12:00:00+00:00"
    assert job["description"] == "Design APIs for distributed teams."
    assert result.metadata.source_urls == [
        "https://www.arbeitnow.com/api/job-board-api?page=1"
    ]
    http.get_html.assert_called_once()


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"query": "frontend"}, ["Frontend Engineer"]),
        ({"location": "munich"}, ["Frontend Engineer"]),
        ({"remote": False}, ["Backend Engineer"]),
        ({"job_type": "contract"}, ["Python Remote Engineer"]),
    ],
)
def test_filters_are_applied_independently(kwargs, expected):
    scraper = ArbeitnowScraper()
    _mock_sync(scraper, _response("page1.json"), _response("page2.json"))

    result = scraper.scrape(max_pages=2, **kwargs)

    assert [job["title"] for job in result.data] == expected


def test_scrape_paginates_deduplicates_and_honors_max_results():
    scraper = ArbeitnowScraper()
    http = _mock_sync(scraper, _response("page1.json"), _response("page2.json"))

    result = scraper.scrape(max_pages=2, max_results=10)

    assert [job["title"] for job in result.data] == [
        "Backend Engineer",
        "Python Remote Engineer",
        "Frontend Engineer",
    ]
    assert result.metadata.total_pages == 2
    assert http.get_html.call_count == 2


def test_missing_fields_are_skipped_or_normalized_to_empty_values():
    payload = json.dumps(
        {
            "data": [
                {"company_name": "Missing title"},
                {"title": "Missing URL"},
                {"title": "Minimal job", "url": "/jobs/minimal"},
            ],
            "links": {"next": None},
        }
    )
    scraper = ArbeitnowScraper()
    _mock_sync(scraper, payload)

    result = scraper.scrape()

    assert result.data == [
        {
            "title": "Minimal job",
            "company": None,
            "location": None,
            "url": "https://www.arbeitnow.com/jobs/minimal",
            "tags": [],
            "job_type": None,
            "job_types": [],
            "remote": False,
            "created_at": None,
            "description": None,
        }
    ]


def test_invalid_json_is_returned_as_scrape_error():
    scraper = ArbeitnowScraper()
    _mock_sync(scraper, "not-json")

    result = scraper.scrape()

    assert result.data == []
    assert len(result.errors) == 1
    assert "Expecting value" in result.errors[0].message


def test_http_error_is_returned_as_scrape_error():
    scraper = ArbeitnowScraper()
    http = MagicMock()
    http.get_html.side_effect = TimeoutError("API unavailable")
    scraper._http = http

    result = scraper.scrape()

    assert result.data == []
    assert result.errors[0].message == "API unavailable"
    assert result.errors[0].url.endswith("?page=1")


def test_invalid_payload_shape_is_returned_as_scrape_error():
    scraper = ArbeitnowScraper()
    _mock_sync(scraper, json.dumps({"data": {"job": "not-a-list"}}))

    result = scraper.scrape()

    assert result.data == []
    assert "'data' must be a list" in result.errors[0].message


@pytest.mark.anyio
async def test_scrape_async_uses_mocked_json_http_client():
    scraper = ArbeitnowScraper()
    http = _mock_async(scraper, _response("page1.json"))

    result = await scraper.scrape_async(query="backend")

    assert [job["title"] for job in result.data] == ["Backend Engineer"]
    assert http.get_html.await_count == 1
    assert http.get_html.await_args.args[0].endswith("?page=1")


def test_fixture_is_valid_json():
    json.loads(_response("page1.json"))
    json.loads(_response("page2.json"))
