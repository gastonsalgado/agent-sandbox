"""Policy engine. Loads rules from YAML, evaluates requests."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import yaml


class Action(Enum):
    ALLOW = "allow"
    DENY = "deny"
    APPROVAL = "approval"


@dataclass(frozen=True)
class Decision:
    action: Action
    reason: str


@dataclass(frozen=True)
class Rule:
    match: dict[str, str]
    action: Action
    label: str = ""


def load_rules(path: Path) -> list[Rule]:
    """Load policy rules from YAML file."""
    data = yaml.safe_load(path.read_text())
    rules = []
    for entry in data.get("rules", []):
        rules.append(Rule(
            match=entry["match"],
            action=Action(entry["action"]),
            label=entry.get("label", ""),
        ))
    return rules


def evaluate(fields: dict[str, str], rules: list[Rule]) -> Decision:
    """Evaluate request fields against rules. First match wins. Default deny."""
    for rule in rules:
        if _matches(fields, rule.match):
            return Decision(
                action=rule.action,
                reason=rule.label or str(rule.match),
            )
    return Decision(action=Action.DENY, reason="no matching rule")


def _matches(fields: dict[str, str], match: dict[str, str]) -> bool:
    """All match conditions must be satisfied."""
    for key, pattern in match.items():
        value = fields.get(key, "")
        if pattern == "*":
            continue
        if key.endswith("_contains"):
            actual_key = key.removesuffix("_contains")
            if pattern not in fields.get(actual_key, ""):
                return False
        elif value != pattern:
            return False
    return True
