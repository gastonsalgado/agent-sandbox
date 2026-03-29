import time
import pytest
from shared.approval import ApprovalService, _Grant


class TestGrantChecking:
    def test_active_grant_auto_approves(self):
        service = ApprovalService()
        service.create_grant("git push", ttl=60)
        assert service._check_grant("git push") is True

    def test_expired_grant_returns_false(self):
        service = ApprovalService()
        service._grants.append(_Grant("git push", time.time() - 10))
        assert service._check_grant("git push") is False

    def test_grant_pattern_is_substring_match(self):
        service = ApprovalService()
        service.create_grant("git push", ttl=60)
        assert service._check_grant("git push to origin/main") is True

    def test_no_grant_returns_false(self):
        service = ApprovalService()
        assert service._check_grant("git push") is False

    def test_expired_grants_are_cleaned_up(self):
        service = ApprovalService()
        service._grants.append(_Grant("old", time.time() - 10))
        service._grants.append(_Grant("current", time.time() + 60))
        service._check_grant("anything")
        assert len(service._grants) == 1
        assert service._grants[0].pattern == "current"


class TestRequestApproval:
    def test_grant_hit_skips_prompt(self):
        service = ApprovalService()
        service.create_grant("git push", ttl=60)
        assert service.request_approval("git push", "POST github.com") is True

    def test_user_approves_with_y(self, monkeypatch):
        service = ApprovalService()
        monkeypatch.setattr("builtins.input", lambda: "y")
        assert service.request_approval("git push", "POST github.com") is True

    def test_user_denies_with_n(self, monkeypatch):
        service = ApprovalService()
        monkeypatch.setattr("builtins.input", lambda: "n")
        assert service.request_approval("git push", "POST github.com") is False

    def test_user_grants_with_g(self, monkeypatch):
        service = ApprovalService()
        monkeypatch.setattr("builtins.input", lambda: "g")
        result = service.request_approval("git push", "POST github.com")
        assert result is True
        assert service._check_grant("git push") is True

    def test_unknown_input_denies(self, monkeypatch):
        service = ApprovalService()
        monkeypatch.setattr("builtins.input", lambda: "maybe")
        assert service.request_approval("git push", "POST github.com") is False

    def test_empty_input_denies(self, monkeypatch):
        service = ApprovalService()
        monkeypatch.setattr("builtins.input", lambda: "")
        assert service.request_approval("git push", "POST github.com") is False


class TestModuleFunctions:
    def test_module_level_request_approval_uses_singleton(self, monkeypatch):
        from shared.approval import request_approval, create_grant
        create_grant("test pattern", ttl=60)
        assert request_approval("test pattern", "detail") is True
