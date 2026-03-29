"""Structured JSONL audit logging with size-based rotation."""

import json
import logging
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger("audit")

AUDIT_PATH = Path(os.environ.get("AUDIT_LOG", "/var/log/sandbox/audit.jsonl"))
MAX_SIZE_BYTES = int(os.environ.get("AUDIT_MAX_SIZE", str(10 * 1024 * 1024)))  # 10MB


@dataclass
class AuditEntry:
    action: str          # ALLOW, DENY, APPROVED, DENIED
    client_id: str
    reason: str
    fields: dict         # domain/method/path or tool/params
    timestamp: float = 0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()


def log(entry: AuditEntry) -> None:
    """Append entry to audit log. Rotate if over max size."""
    try:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        _rotate_if_needed()
        with open(AUDIT_PATH, "a") as f:
            f.write(json.dumps(asdict(entry)) + "\n")
    except Exception as e:
        logger.error(f"Audit write failed: {e}")


def _rotate_if_needed() -> None:
    """Rename current log to .1 if over size limit."""
    if not AUDIT_PATH.exists():
        return
    if AUDIT_PATH.stat().st_size < MAX_SIZE_BYTES:
        return

    rotated = AUDIT_PATH.with_suffix(".jsonl.1")
    if rotated.exists():
        rotated.unlink()
    AUDIT_PATH.rename(rotated)
