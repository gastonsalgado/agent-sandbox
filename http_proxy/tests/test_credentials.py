"""Tests for HTTP credential injection."""

from unittest.mock import MagicMock
import base64

import pytest

import credentials
import providers


@pytest.fixture
def flow():
    """Create a minimal mock HTTPFlow."""
    from mitmproxy.http import Headers
    f = MagicMock()
    f.request.headers = Headers()
    return f


class TestInject:
    def test_github_basic_auth(self, flow, monkeypatch):
        monkeypatch.setattr(credentials, "get_token", lambda k: "gh-token" if k == "github" else None)
        flow.request.pretty_host = "github.com"

        credentials.inject(flow)

        expected = base64.b64encode(b"x-access-token:gh-token").decode()
        assert flow.request.headers["Authorization"] == f"Basic {expected}"

    def test_github_subdomain(self, flow, monkeypatch):
        monkeypatch.setattr(credentials, "get_token", lambda k: "gh-token" if k == "github" else None)
        flow.request.pretty_host = "api.github.com"

        credentials.inject(flow)

        assert "Basic" in flow.request.headers["Authorization"]

    def test_gcp_bearer(self, flow, monkeypatch):
        monkeypatch.setattr(credentials, "get_token", lambda k: "gcp-token" if k == "gcp" else None)
        flow.request.pretty_host = "storage.googleapis.com"
        flow.request.path = "/v1/buckets"

        credentials.inject(flow)

        assert flow.request.headers["Authorization"] == "Bearer gcp-token"

    def test_gcp_skips_claude_code(self, flow, monkeypatch):
        monkeypatch.setattr(credentials, "get_token", lambda k: "gcp-token" if k == "gcp" else None)
        flow.request.pretty_host = "storage.googleapis.com"
        flow.request.path = "/claude-code/updates"

        credentials.inject(flow)

        assert "Authorization" not in flow.request.headers

    def test_slack_bearer(self, flow, monkeypatch):
        monkeypatch.setattr(credentials, "get_token", lambda k: "sl-token" if k == "slack" else None)
        flow.request.pretty_host = "api.slack.com"

        credentials.inject(flow)

        assert flow.request.headers["Authorization"] == "Bearer sl-token"

    def test_no_header_when_token_none(self, flow, monkeypatch):
        monkeypatch.setattr(credentials, "get_token", lambda k: None)
        flow.request.pretty_host = "github.com"

        credentials.inject(flow)

        assert "Authorization" not in flow.request.headers

    def test_unknown_domain_no_header(self, flow, monkeypatch):
        monkeypatch.setattr(credentials, "get_token", lambda k: "some-token")
        flow.request.pretty_host = "example.com"

        credentials.inject(flow)

        assert "Authorization" not in flow.request.headers
