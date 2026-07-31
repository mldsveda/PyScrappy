"""Tests for pyscrappy.core.browser."""

from unittest.mock import MagicMock, patch

import pytest

from pyscrappy.core.browser import BrowserManager
from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.exceptions import BrowserNotInstalledError


class TestBrowserManagerInit:
    def test_default_config(self):
        bm = BrowserManager()
        assert bm.config.timeout == 30.0
        assert bm._pw is None
        assert bm._browser is None

    def test_custom_config(self):
        config = ScraperConfig(headless=False, timeout=60.0)
        bm = BrowserManager(config)
        assert bm.config.headless is False
        assert bm.config.timeout == 60.0


class TestBrowserManagerImportError:
    def test_start_raises_browser_not_installed_when_no_playwright(self, monkeypatch):
        import builtins

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if "playwright" in name:
                raise ImportError("no playwright")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        bm = BrowserManager()
        with pytest.raises(BrowserNotInstalledError):
            bm._start()


class TestBrowserManagerClose:
    def test_close_when_nothing_started(self):
        bm = BrowserManager()
        bm.close()  # should not raise

    def test_close_cleans_up(self):
        bm = BrowserManager()
        mock_browser = MagicMock()
        mock_pw = MagicMock()
        bm._browser = mock_browser
        bm._pw = mock_pw

        bm.close()

        mock_browser.close.assert_called_once()
        mock_pw.stop.assert_called_once()
        assert bm._browser is None
        assert bm._pw is None


class TestBrowserManagerContextManager:
    def test_context_manager_calls_close(self):
        bm = BrowserManager()
        mock_browser = MagicMock()
        mock_pw = MagicMock()

        with patch.object(bm, "_start"):
            with bm:
                bm._browser = mock_browser
                bm._pw = mock_pw

        mock_browser.close.assert_called_once()
        mock_pw.stop.assert_called_once()


class TestBrowserManagerGetHtml:
    def test_get_html_calls_browser(self):
        bm = BrowserManager()
        mock_page = MagicMock()
        mock_page.content.return_value = "<html>rendered</html>"
        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context
        bm._browser = mock_browser

        html = bm.get_html("https://example.com")

        assert html == "<html>rendered</html>"
        mock_page.goto.assert_called_once()
        mock_page.close.assert_called_once()
        mock_context.close.assert_called_once()

    def test_get_html_with_scroll(self):
        bm = BrowserManager()
        mock_page = MagicMock()
        mock_page.content.return_value = "<html>scrolled</html>"
        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context
        bm._browser = mock_browser

        html = bm.get_html("https://example.com", scroll_pages=3)

        assert html == "<html>scrolled</html>"
        assert mock_page.evaluate.call_count == 3
        assert mock_page.wait_for_timeout.call_count == 3

    def test_get_html_cleans_up_on_error(self):
        bm = BrowserManager()
        mock_page = MagicMock()
        mock_page.goto.side_effect = Exception("timeout")
        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context
        bm._browser = mock_browser

        with pytest.raises(Exception, match="timeout"):
            bm.get_html("https://example.com")

        mock_page.close.assert_called_once()
        mock_context.close.assert_called_once()


class TestBrowserManagerScreenshot:
    def test_screenshot_calls_browser(self):
        bm = BrowserManager()
        mock_page = MagicMock()
        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context
        bm._browser = mock_browser

        bm.screenshot("https://example.com", "/tmp/test.png")

        mock_page.goto.assert_called_once()
        mock_page.screenshot.assert_called_once_with(path="/tmp/test.png", full_page=True)
        mock_page.close.assert_called_once()
        mock_context.close.assert_called_once()

    def test_screenshot_partial_page(self):
        bm = BrowserManager()
        mock_page = MagicMock()
        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context
        bm._browser = mock_browser

        bm.screenshot("https://example.com", "/tmp/test.png", full_page=False)

        mock_page.screenshot.assert_called_once_with(path="/tmp/test.png", full_page=False)
