"""Terminal-based approval with temporary grants."""

import sys
import threading
import time
from dataclasses import dataclass


@dataclass
class _Grant:
    pattern: str
    expires: float


class ApprovalService:
    """Thread-safe approval with TTL-based grants."""

    def __init__(self):
        self._grants: list[_Grant] = []
        self._lock = threading.Lock()

    def request_approval(self, label: str, detail: str) -> bool:
        """Check grants first, then prompt terminal. Returns True if approved."""
        if self._check_grant(label):
            return True

        sys.stderr.write(f"\n{'='*60}\n")
        sys.stderr.write(f"  APPROVAL REQUIRED: {label}\n")
        sys.stderr.write(f"  Detail: {detail}\n")
        sys.stderr.write(f"{'='*60}\n")
        sys.stderr.write("  [y] Approve  [g] Approve + grant 5min  [n] Deny\n")
        sys.stderr.write("  > ")
        sys.stderr.flush()

        response = input().strip().lower()

        if response == "g":
            self.create_grant(label, ttl=300)
            return True

        return response == "y"

    def create_grant(self, pattern: str, ttl: int = 300) -> None:
        with self._lock:
            self._grants.append(_Grant(pattern, time.time() + ttl))

    def _check_grant(self, label: str) -> bool:
        with self._lock:
            now = time.time()
            self._grants = [g for g in self._grants if g.expires > now]
            return any(g.pattern in label for g in self._grants)


_service = ApprovalService()


def request_approval(label: str, detail: str) -> bool:
    return _service.request_approval(label, detail)


def create_grant(pattern: str, ttl: int = 300) -> None:
    _service.create_grant(pattern, ttl)
