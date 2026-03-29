"""mitmproxy addon. Single class, delegates to shared libs."""

import logging
import os
from pathlib import Path

from mitmproxy import http

from shared.policy import Action, evaluate, load_rules
from shared.approval import request_approval
from shared.audit import log, AuditEntry
from credentials import inject

logger = logging.getLogger("http_proxy")

POLICY_PATH = Path(os.environ.get("HTTP_POLICY", "/etc/sandbox/http_policy.yaml"))
VAULT_DIR = Path(os.environ.get("VAULT_DIR", "/vault"))
CLIENT_ID = os.environ.get("CLIENT_ID", "default")


class HttpPolicyAddon:
    def __init__(self):
        self.rules = load_rules(POLICY_PATH)

    def request(self, flow: http.HTTPFlow):
        fields = {
            "domain": flow.request.pretty_host,
            "method": flow.request.method,
            "path": flow.request.path,
        }

        decision = evaluate(fields, self.rules)

        if decision.action == Action.ALLOW:
            try:
                inject(flow, VAULT_DIR, CLIENT_ID)
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
                    inject(flow, VAULT_DIR, CLIENT_ID)
                except Exception:
                    pass  # No credentials for this domain — proceed without injection
                log(AuditEntry("APPROVED", CLIENT_ID, decision.reason, fields))
            else:
                flow.response = http.Response.make(
                    403, f'{{"error":"denied","reason":"{decision.reason}"}}'
                )
                log(AuditEntry("DENIED", CLIENT_ID, decision.reason, fields))


addons = [HttpPolicyAddon()]
