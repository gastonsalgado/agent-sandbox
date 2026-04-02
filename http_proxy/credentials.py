"""HTTP-specific credential injection into request headers."""

import base64

from mitmproxy import http

from providers import get_token


def inject(flow: http.HTTPFlow) -> None:
    """Inject credentials based on target domain."""
    host = flow.request.pretty_host

    if host == "github.com" or host.endswith(".github.com"):
        token = get_token("github")
        if token:
            encoded = base64.b64encode(
                f"x-access-token:{token}".encode()
            ).decode()
            flow.request.headers["Authorization"] = f"Basic {encoded}"

    elif host.endswith(".googleapis.com") or host == "googleapis.com":
        if "claude-code" in flow.request.path:
            return
        token = get_token("gcp")
        if token:
            flow.request.headers["Authorization"] = f"Bearer {token}"

    elif host == "slack.com" or host.endswith(".slack.com"):
        token = get_token("slack")
        if token:
            flow.request.headers["Authorization"] = f"Bearer {token}"
