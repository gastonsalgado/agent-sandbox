"""Terminal-based approval with temporary grants."""

import os
import signal
import sys
import threading
import time
from dataclasses import dataclass

APPROVAL_TIMEOUT = int(os.environ.get("APPROVAL_TIMEOUT", "30"))


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
        """Check grants first, then prompt terminal with timeout. Returns True if approved."""
        if self._check_grant(label):
            return True

        sys.stderr.write(f"\n{'='*60}\n")
        sys.stderr.write(f"  APPROVAL REQUIRED: {label}\n")
        sys.stderr.write(f"  Detail: {detail}\n")
        sys.stderr.write(f"  Timeout: {APPROVAL_TIMEOUT}s (auto-deny)\n")
        sys.stderr.write(f"{'='*60}\n")
        sys.stderr.write("  [y] Approve  [g] Approve + grant 5min  [n] Deny\n")
        sys.stderr.write("  > ")
        sys.stderr.flush()

        response = _read_with_timeout(APPROVAL_TIMEOUT)
        if response is None:
            sys.stderr.write("\n  ⏱ Timeout — denied\n")
            sys.stderr.flush()
            return False

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


class _TimeoutError(Exception):
    pass


def _read_with_timeout(timeout: int) -> str | None:
    """Read a line from stdin with timeout using SIGALRM."""
    def _handler(signum, frame):
        raise _TimeoutError()

    old_handler = signal.signal(signal.SIGALRM, _handler)
    signal.alarm(timeout)
    try:
        response = input().strip().lower()
        signal.alarm(0)
        return response
    except (_TimeoutError, EOFError):
        return None
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


_service = ApprovalService()


def request_approval(label: str, detail: str) -> bool:
    return _service.request_approval(label, detail)


def create_grant(pattern: str, ttl: int = 300) -> None:
    _service.create_grant(pattern, ttl)
