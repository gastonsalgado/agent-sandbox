import pytest
from shared.vault import CredentialNotFoundError, read_credential, list_credentials


class TestReadCredential:
    def test_reads_existing_credential(self, tmp_path):
        (tmp_path / "acme").mkdir()
        (tmp_path / "acme" / "github_token").write_text("ghp_abc123\n")
        assert read_credential(tmp_path, "acme", "github_token") == "ghp_abc123"

    def test_strips_whitespace_and_newlines(self, tmp_path):
        (tmp_path / "acme").mkdir()
        (tmp_path / "acme" / "token").write_text("  mytoken  \n\n")
        assert read_credential(tmp_path, "acme", "token") == "mytoken"

    def test_missing_client_dir_raises(self, tmp_path):
        with pytest.raises(CredentialNotFoundError, match="Credential not found"):
            read_credential(tmp_path, "nonexistent", "token")

    def test_missing_key_file_raises(self, tmp_path):
        (tmp_path / "acme").mkdir()
        with pytest.raises(CredentialNotFoundError, match="Credential not found"):
            read_credential(tmp_path, "acme", "nonexistent")

    def test_empty_credential_raises(self, tmp_path):
        (tmp_path / "acme").mkdir()
        (tmp_path / "acme" / "token").write_text("  \n")
        with pytest.raises(CredentialNotFoundError, match="Credential is empty"):
            read_credential(tmp_path, "acme", "token")

    def test_path_traversal_blocked(self, tmp_path):
        (tmp_path / "acme").mkdir()
        with pytest.raises(CredentialNotFoundError, match="Invalid credential path"):
            read_credential(tmp_path, "acme", "../../etc/passwd")


class TestListCredentials:
    def test_lists_available_keys(self, tmp_path):
        (tmp_path / "acme").mkdir()
        (tmp_path / "acme" / "github_token").write_text("gh_123")
        (tmp_path / "acme" / "slack_token").write_text("xoxb_123")
        result = list_credentials(tmp_path, "acme")
        assert sorted(result) == ["github_token", "slack_token"]

    def test_empty_for_nonexistent_client(self, tmp_path):
        assert list_credentials(tmp_path, "nonexistent") == []

    def test_ignores_subdirectories(self, tmp_path):
        (tmp_path / "acme").mkdir()
        (tmp_path / "acme" / "github_token").write_text("gh_123")
        (tmp_path / "acme" / "subdir").mkdir()
        result = list_credentials(tmp_path, "acme")
        assert result == ["github_token"]
