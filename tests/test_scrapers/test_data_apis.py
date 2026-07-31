"""Tests for the data-API scrapers: Crypto, Currency, Dictionary."""

import json
from unittest.mock import MagicMock

from pyscrappy.scrapers.crypto import CryptoScraper
from pyscrappy.scrapers.currency import CurrencyScraper
from pyscrappy.scrapers.dictionary import DictionaryScraper


def _mock(scraper, *responses):
    scraper._http = MagicMock()
    scraper._http.get_html.side_effect = list(responses)
    return scraper


class TestCrypto:
    def test_top_coins(self):
        payload = json.dumps(
            [
                {
                    "id": "bitcoin",
                    "name": "Bitcoin",
                    "symbol": "btc",
                    "current_price": 64000,
                    "market_cap": 1200000000000,
                    "market_cap_rank": 1,
                    "price_change_percentage_24h": 1.5,
                    "total_volume": 30000000000,
                    "high_24h": 64500,
                    "low_24h": 63000,
                }
            ]
        )
        s = _mock(CryptoScraper(), payload)
        r = s.scrape(max_results=1)
        assert len(r.data) == 1
        c = r.data[0]
        assert c["name"] == "Bitcoin"
        assert c["symbol"] == "BTC"
        assert c["price"] == 64000
        assert c["currency"] == "USD"
        assert c["change_24h_pct"] == 1.5

    def test_query_resolves_ids(self):
        search = json.dumps({"coins": [{"id": "ethereum"}]})
        markets = json.dumps(
            [{"id": "ethereum", "name": "Ethereum", "symbol": "eth", "current_price": 1800}]
        )
        s = _mock(CryptoScraper(), search, markets)
        r = s.scrape(query="eth")
        assert r.data[0]["name"] == "Ethereum"
        # the markets URL should carry the resolved id
        assert "ids=ethereum" in s._http.get_html.call_args[0][0]


class TestCurrency:
    def test_rates_and_conversion(self):
        payload = json.dumps(
            {
                "result": "success",
                "base_code": "USD",
                "time_last_update_utc": "Sat, 01 Jan 2026 00:00:00 +0000",
                "rates": {"EUR": 0.9, "GBP": 0.8, "JPY": 150.0},
            }
        )
        s = _mock(CurrencyScraper(), payload)
        r = s.scrape(base="USD", to="EUR,GBP", amount=100)
        assert len(r.data) == 2  # only EUR + GBP
        by_code = {row["currency"]: row for row in r.data}
        assert by_code["EUR"]["converted"] == 90.0
        assert by_code["GBP"]["converted"] == 80.0

    def test_api_error(self):
        s = _mock(
            CurrencyScraper(), json.dumps({"result": "error", "error-type": "unsupported-code"})
        )
        r = s.scrape(base="XXX")
        assert r.data == []
        assert "unsupported-code" in r.errors[0].message


class TestDictionary:
    def test_definitions(self):
        payload = json.dumps(
            [
                {
                    "word": "test",
                    "phonetic": "/tɛst/",
                    "meanings": [
                        {
                            "partOfSpeech": "noun",
                            "definitions": [
                                {
                                    "definition": "A procedure to establish quality.",
                                    "example": "a test of skill",
                                    "synonyms": ["trial"],
                                },
                            ],
                        }
                    ],
                }
            ]
        )
        s = _mock(DictionaryScraper(), payload)
        r = s.scrape(word="test")
        assert len(r.data) == 1
        d = r.data[0]
        assert d["word"] == "test"
        assert d["part_of_speech"] == "noun"
        assert d["example"] == "a test of skill"
        assert d["synonyms"] == ["trial"]

    def test_word_not_found(self):
        # API returns a dict with "title" when not found
        s = _mock(DictionaryScraper(), json.dumps({"title": "No Definitions Found"}))
        r = s.scrape(word="zzxqq")
        assert r.data == []
        assert "No Definitions" in r.errors[0].message
