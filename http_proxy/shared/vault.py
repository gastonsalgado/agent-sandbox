"""Read credentials from vault directory."""

from pathlib import Path


class CredentialNotFoundError(Exception):
    pass


def read_credential(vault_dir: Path, client_id: str, key: str) -> str:
    """Read /vault/{client_id}/{key}. Raises if missing or empty."""
    path = vault_dir / client_id / key

    # Prevent path traversal attacks
    resolved = path.resolve()
    if not str(resolved).startswith(str(vault_dir.resolve())):
        raise CredentialNotFoundError(f"Invalid credential path: {key}")

    if not path.is_file():
        raise CredentialNotFoundError(f"Credential not found: {path}")

    value = path.read_text().strip()

    if not value:
        raise CredentialNotFoundError(f"Credential is empty: {path}")

    return value


def list_credentials(vault_dir: Path, client_id: str) -> list[str]:
    """List available credential keys for a client."""
    client_dir = vault_dir / client_id
    if not client_dir.is_dir():
        return []
    return [f.name for f in client_dir.iterdir() if f.is_file()]
