import pytest
from unittest.mock import MagicMock, patch


def _make_flow(content: bytes | None) -> MagicMock:
    flow = MagicMock()
    flow.request.content = content
    return flow


@pytest.fixture(autouse=True)
def _patch_addon_init(monkeypatch, tmp_path):
    """Prevent HttpPolicyAddon from loading a real policy file on import."""
    policy = tmp_path / "policy.yaml"
    policy.write_text("rules: []\n")
    monkeypatch.setenv("HTTP_POLICY", str(policy))


def _import():
    import addon
    return addon._safe_body, addon.MAX_BODY_BYTES


class TestSafeBody:
    def test_normal_text(self):
        _safe_body, _ = _import()
        flow = _make_flow(b'{"query": "mutation { foo }"}')
        assert _safe_body(flow) == '{"query": "mutation { foo }"}'

    def test_no_body(self):
        _safe_body, _ = _import()
        flow = _make_flow(None)
        assert _safe_body(flow) == ""

    def test_empty_body(self):
        _safe_body, _ = _import()
        flow = _make_flow(b"")
        assert _safe_body(flow) == ""

    def test_exceeds_max_size(self):
        _safe_body, MAX_BODY_BYTES = _import()
        flow = _make_flow(b"x" * (MAX_BODY_BYTES + 1))
        assert _safe_body(flow) == ""

    def test_exactly_max_size(self):
        _safe_body, MAX_BODY_BYTES = _import()
        flow = _make_flow(b"x" * MAX_BODY_BYTES)
        assert _safe_body(flow) == "x" * MAX_BODY_BYTES

    def test_binary_content(self):
        _safe_body, _ = _import()
        flow = _make_flow(b"\x80\x81\x82\xff")
        assert _safe_body(flow) == ""

    def test_utf8_with_special_chars(self):
        _safe_body, _ = _import()
        flow = _make_flow('{"query": "café"}'.encode("utf-8"))
        assert _safe_body(flow) == '{"query": "café"}'
