"""Tests for pyscrappy.core.config."""

from pyscrappy.core.config import _DEFAULT_USER_AGENTS, ScraperConfig


class TestScraperConfig:
    def test_default_values(self):
        config = ScraperConfig()
        assert config.timeout == 30.0
        assert config.max_retries == 3
        assert config.retry_delay == 1.0
        assert config.retry_jitter is True
        assert config.rate_limit == 1.0
        assert config.proxy is None
        assert config.render_js is False
        assert config.headless is True
        assert config.verify_ssl is True

    def test_default_user_agents(self):
        config = ScraperConfig()
        assert len(config.user_agents) == 5
        assert config.user_agents == list(_DEFAULT_USER_AGENTS)

    def test_user_agents_are_independent_copies(self):
        c1 = ScraperConfig()
        c2 = ScraperConfig()
        c1.user_agents.append("custom-agent")
        assert len(c2.user_agents) == 5

    def test_custom_values(self):
        config = ScraperConfig(
            timeout=10.0,
            max_retries=5,
            retry_delay=2.0,
            retry_jitter=False,
            rate_limit=0.5,
            proxy="http://proxy:8080",
            render_js="auto",
            headless=False,
            verify_ssl=False,
        )
        assert config.timeout == 10.0
        assert config.max_retries == 5
        assert config.retry_delay == 2.0
        assert config.retry_jitter is False
        assert config.rate_limit == 0.5
        assert config.proxy == "http://proxy:8080"
        assert config.render_js == "auto"
        assert config.headless is False
        assert config.verify_ssl is False

    def test_custom_user_agents(self):
        agents = ["Agent/1.0", "Agent/2.0"]
        config = ScraperConfig(user_agents=agents)
        assert config.user_agents == agents

    def test_render_js_auto(self):
        config = ScraperConfig(render_js="auto")
        assert config.render_js == "auto"

    def test_render_js_true(self):
        config = ScraperConfig(render_js=True)
        assert config.render_js is True
