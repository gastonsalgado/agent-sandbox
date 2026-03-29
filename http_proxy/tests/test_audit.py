import json
import pytest
from shared.audit import AuditEntry, log, _rotate_if_needed, AUDIT_PATH, MAX_SIZE_BYTES


class TestAuditEntry:
    def test_timestamp_auto_set(self):
        entry = AuditEntry("ALLOW", "acme", "github read", {"domain": "github.com"})
        assert entry.timestamp > 0

    def test_explicit_timestamp_preserved(self):
        entry = AuditEntry("ALLOW", "acme", "test", {}, timestamp=123.0)
        assert entry.timestamp == 123.0


class TestLog:
    def test_creates_file_and_writes_entry(self, tmp_path, monkeypatch):
        log_path = tmp_path / "audit.jsonl"
        monkeypatch.setattr("shared.audit.AUDIT_PATH", log_path)
        log(AuditEntry("ALLOW", "acme", "github read", {"domain": "github.com"}))
        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["action"] == "ALLOW"
        assert entry["client_id"] == "acme"
        assert entry["reason"] == "github read"
        assert entry["fields"] == {"domain": "github.com"}
        assert entry["timestamp"] > 0

    def test_appends_multiple_entries(self, tmp_path, monkeypatch):
        log_path = tmp_path / "audit.jsonl"
        monkeypatch.setattr("shared.audit.AUDIT_PATH", log_path)
        log(AuditEntry("ALLOW", "acme", "first", {}))
        log(AuditEntry("DENY", "acme", "second", {}))
        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["reason"] == "first"
        assert json.loads(lines[1])["reason"] == "second"

    def test_creates_parent_directories(self, tmp_path, monkeypatch):
        log_path = tmp_path / "subdir" / "nested" / "audit.jsonl"
        monkeypatch.setattr("shared.audit.AUDIT_PATH", log_path)
        log(AuditEntry("ALLOW", "acme", "test", {}))
        assert log_path.exists()


class TestRotation:
    def test_rotates_when_over_limit(self, tmp_path, monkeypatch):
        log_path = tmp_path / "audit.jsonl"
        monkeypatch.setattr("shared.audit.AUDIT_PATH", log_path)
        monkeypatch.setattr("shared.audit.MAX_SIZE_BYTES", 50)
        log(AuditEntry("ALLOW", "acme", "big entry", {"data": "x" * 100}))
        log(AuditEntry("ALLOW", "acme", "after rotation", {"data": "y"}))
        rotated = tmp_path / "audit.jsonl.1"
        assert rotated.exists()
        current_lines = log_path.read_text().strip().split("\n")
        assert json.loads(current_lines[-1])["reason"] == "after rotation"

    def test_overwrites_previous_rotated_file(self, tmp_path, monkeypatch):
        log_path = tmp_path / "audit.jsonl"
        rotated = tmp_path / "audit.jsonl.1"
        monkeypatch.setattr("shared.audit.AUDIT_PATH", log_path)
        monkeypatch.setattr("shared.audit.MAX_SIZE_BYTES", 50)
        rotated.write_text("old rotated content\n")
        log(AuditEntry("ALLOW", "acme", "big entry", {"data": "x" * 100}))
        log(AuditEntry("ALLOW", "acme", "new", {}))
        assert "old rotated content" not in rotated.read_text()

    def test_no_rotation_under_limit(self, tmp_path, monkeypatch):
        log_path = tmp_path / "audit.jsonl"
        monkeypatch.setattr("shared.audit.AUDIT_PATH", log_path)
        monkeypatch.setattr("shared.audit.MAX_SIZE_BYTES", 10 * 1024 * 1024)
        log(AuditEntry("ALLOW", "acme", "small", {}))
        log(AuditEntry("ALLOW", "acme", "also small", {}))
        rotated = tmp_path / "audit.jsonl.1"
        assert not rotated.exists()
