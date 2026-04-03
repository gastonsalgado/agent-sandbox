"""mitmproxy addon. Single class, delegates to shared libs."""

import logging
import os
from pathlib import Path

from mitmproxy import http

from shared.policy import Action, evaluate, load_rules
from shared.approval import request_approval
from shared.audit import log, AuditEntry
from credentials import inject
import providers

logger = logging.getLogger("http_proxy")

POLICY_PATH = Path(os.environ.get("HTTP_POLICY", "/etc/sandbox/http_policy.yaml"))
CLIENT_ID = os.environ.get("CLIENT_ID", "default")
MAX_BODY_BYTES = 1_048_576  # 1MB


def _safe_body(flow: http.HTTPFlow) -> str:
    """Extract request body for matching. Returns '' if too large or binary."""
    content = flow.request.content
    if not content or len(content) > MAX_BODY_BYTES:
        return ""
    try:
        return content.decode("utf-8", errors="strict")
    except (UnicodeDecodeError, ValueError):
        return ""


class HttpPolicyAddon:
    def __init__(self):
        self.rules = load_rules(POLICY_PATH)
        providers.setup()

    def request(self, flow: http.HTTPFlow):
        fields = {
            "domain": flow.request.pretty_host,
            "method": flow.request.method,
            "path": flow.request.path,
        }
        match_fields = {**fields, "body": _safe_body(flow)}

        decision = evaluate(match_fields, self.rules)

        if decision.action == Action.ALLOW:
            try:
                inject(flow)
            except Exception:
                pass  # No credentials for this domain — proceed without injection
            log(AuditEntry("ALLOW", CLIENT_ID, decision.reason, fields))
            return

        if decision.action == Action.DENY:
            flow.response = http.Response.make(
                403, f'{{"error":"blocked","reason":"{decision.reason}"}}'
            )
            log(AuditEntry("DENY", CLIENT_ID, decision.reason, fields))
            return

        if decision.action == Action.APPROVAL:
            summary = f"{fields['method']} {fields['domain']}{fields['path']}"
            approved = request_approval(decision.reason, summary)
            if approved:
                try:
                    inject(flow)
                except Exception:
                    pass  # No credentials for this domain — proceed without injection
                log(AuditEntry("APPROVED", CLIENT_ID, decision.reason, fields))
            else:
                flow.response = http.Response.make(
                    403, f'{{"error":"denied","reason":"{decision.reason}"}}'
                )
                log(AuditEntry("DENIED", CLIENT_ID, decision.reason, fields))


addons = [HttpPolicyAddon()]
