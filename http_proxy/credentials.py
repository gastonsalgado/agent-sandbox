"""HTTP-specific credential injection into request headers."""

import base64
from pathlib import Path

from mitmproxy import http

from shared.vault import read_credential


def inject(flow: http.HTTPFlow, vault_dir: Path, client_id: str) -> None:
    """Inject credentials based on target domain."""
    host = flow.request.pretty_host

    if host == "github.com" or host.endswith(".github.com"):
        token = read_credential(vault_dir, client_id, "github_token")
        encoded = base64.b64encode(
            f"x-access-token:{token}".encode()
        ).decode()
        flow.request.headers["Authorization"] = f"Basic {encoded}"

    elif host.endswith(".googleapis.com") or host == "googleapis.com":
        # Don't inject credentials for Claude Code update checks
        if "claude-code" in flow.request.path:
            return
        token = read_credential(vault_dir, client_id, "gcp_access_token")
        flow.request.headers["Authorization"] = f"Bearer {token}"

    elif host == "slack.com" or host.endswith(".slack.com"):
        token = read_credential(vault_dir, client_id, "slack_token")
        flow.request.headers["Authorization"] = f"Bearer {token}"
