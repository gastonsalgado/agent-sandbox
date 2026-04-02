"""Tests for in-memory token providers."""

import threading
from unittest.mock import MagicMock

import pytest

import providers
from providers import (
    EnvTokenProvider,
    GcpTokenProvider,
)


class TestEnvTokenProvider:
    def test_reads_from_env_var(self, monkeypatch):
        monkeypatch.setenv("TEST_TOKEN", "env-secret")
        p = EnvTokenProvider(env_var="TEST_TOKEN")
        assert p.get_token() == "env-secret"

    def test_caches_after_first_read(self, monkeypatch):
        monkeypatch.setenv("TEST_TOKEN", "first-value")
        p = EnvTokenProvider(env_var="TEST_TOKEN")

        assert p.get_token() == "first-value"

        # Change env var — should still return cached value
        monkeypatch.setenv("TEST_TOKEN", "second-value")
        assert p.get_token() == "first-value"

    def test_raises_when_not_set(self):
        p = EnvTokenProvider(env_var="NONEXISTENT_VAR_XYZ")
        with pytest.raises(ValueError, match="not set"):
            p.get_token()


class TestGcpTokenProvider:
    def _make_credentials(self, token="gcp-token-abc", expired=False):
        creds = MagicMock()
        creds.token = token
        creds.expired = expired
        return creds

    def test_returns_valid_token(self):
        creds = self._make_credentials(token="valid-token", expired=False)
        p = GcpTokenProvider(credentials=creds)
        assert p.get_token() == "valid-token"
        creds.refresh.assert_not_called()

    def test_refreshes_expired_token(self):
        creds = self._make_credentials(expired=True)
        creds.token = "refreshed-token"
        p = GcpTokenProvider(credentials=creds, request_factory=MagicMock)
        p.get_token()
        creds.refresh.assert_called_once()

    def test_refreshes_when_no_token(self):
        creds = self._make_credentials(token=None, expired=False)
        p = GcpTokenProvider(credentials=creds, request_factory=MagicMock)
        p.get_token()
        creds.refresh.assert_called_once()

    def test_thread_safety(self):
        creds = self._make_credentials(token="safe-token", expired=False)
        p = GcpTokenProvider(credentials=creds)
        results = []
        errors = []

        def call():
            try:
                results.append(p.get_token())
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=call) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert all(r == "safe-token" for r in results)


class TestModuleFunctions:
    def test_setup_and_get_token(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "gh-test")
        monkeypatch.setenv("SLACK_TOKEN", "sl-test")

        providers.setup()

        assert providers.get_token("github") == "gh-test"
        assert providers.get_token("slack") == "sl-test"

    def test_get_token_unknown_key(self):
        providers.setup()
        assert providers.get_token("unknown") is None

    def test_get_token_returns_none_on_failure(self):
        providers.setup()
        # GCP provider will fail without real credentials — returns None
        assert providers.get_token("gcp") is None
