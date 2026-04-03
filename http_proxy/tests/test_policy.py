import pytest
from shared.policy import Action, Decision, Rule, evaluate, load_rules, _matches


class TestMatches:
    def test_exact_match(self):
        assert _matches({"domain": "github.com"}, {"domain": "github.com"}) is True

    def test_exact_mismatch(self):
        assert _matches({"domain": "evil.com"}, {"domain": "github.com"}) is False

    def test_wildcard_matches_anything(self):
        assert _matches({"domain": "anything.com"}, {"domain": "*"}) is True

    def test_contains_match(self):
        assert _matches(
            {"path": "/repo.git/git-receive-pack"},
            {"path_contains": "git-receive-pack"},
        ) is True

    def test_contains_mismatch(self):
        assert _matches(
            {"path": "/repo.git/info/refs"},
            {"path_contains": "git-receive-pack"},
        ) is False

    def test_multiple_conditions_all_must_match(self):
        assert _matches(
            {"domain": "github.com", "method": "GET"},
            {"domain": "github.com", "method": "GET"},
        ) is True

    def test_multiple_conditions_partial_mismatch(self):
        assert _matches(
            {"domain": "github.com", "method": "POST"},
            {"domain": "github.com", "method": "GET"},
        ) is False

    def test_missing_field_treated_as_empty_string(self):
        assert _matches({}, {"domain": "github.com"}) is False

    def test_contains_with_missing_field(self):
        assert _matches({}, {"path_contains": "foo"}) is False

    def test_body_contains_match(self):
        assert _matches(
            {"body": '{"query": "mutation { createIssue(input: {}) { id } }"}'},
            {"body_contains": "mutation"},
        ) is True

    def test_body_contains_mismatch(self):
        assert _matches(
            {"body": '{"query": "query { viewer { login } }"}'},
            {"body_contains": "mutation"},
        ) is False

    def test_body_contains_empty_body(self):
        assert _matches({"body": ""}, {"body_contains": "mutation"}) is False

    def test_body_contains_combined_with_path(self):
        assert _matches(
            {"path": "/graphql", "body": '{"query": "mutation { delete }"}'},
            {"path": "/graphql", "body_contains": "mutation"},
        ) is True


class TestEvaluate:
    def test_first_match_wins(self):
        rules = [
            Rule(match={"domain": "github.com", "method": "GET"}, action=Action.ALLOW, label="read"),
            Rule(match={"domain": "github.com"}, action=Action.DENY, label="default"),
        ]
        result = evaluate({"domain": "github.com", "method": "GET", "path": "/"}, rules)
        assert result.action == Action.ALLOW
        assert result.reason == "read"

    def test_default_deny_when_no_rules_match(self):
        result = evaluate({"domain": "evil.com"}, [])
        assert result.action == Action.DENY
        assert result.reason == "no matching rule"

    def test_approval_action(self):
        rules = [Rule(match={"domain": "github.com", "path_contains": "git-receive-pack"}, action=Action.APPROVAL, label="git push")]
        result = evaluate({"domain": "github.com", "path": "/repo.git/git-receive-pack"}, rules)
        assert result.action == Action.APPROVAL
        assert result.reason == "git push"

    def test_reason_falls_back_to_match_dict_if_no_label(self):
        rules = [Rule(match={"domain": "github.com"}, action=Action.ALLOW)]
        result = evaluate({"domain": "github.com"}, rules)
        assert result.action == Action.ALLOW
        assert "github.com" in result.reason

    def test_works_for_mcp_tool_fields(self):
        rules = [
            Rule(match={"tool": "slack_read_channel"}, action=Action.ALLOW),
            Rule(match={"tool": "slack_send_message"}, action=Action.APPROVAL, label="send slack"),
            Rule(match={"tool": "*"}, action=Action.DENY, label="unknown tool"),
        ]
        assert evaluate({"tool": "slack_read_channel"}, rules).action == Action.ALLOW
        assert evaluate({"tool": "slack_send_message"}, rules).action == Action.APPROVAL
        assert evaluate({"tool": "unknown_tool"}, rules).action == Action.DENY


class TestLoadRules:
    def test_load_from_yaml(self, tmp_path):
        policy = tmp_path / "policy.yaml"
        policy.write_text(
            "rules:\n"
            '  - match: {domain: "github.com", method: GET}\n'
            "    action: allow\n"
            "    label: github read\n"
            '  - match: {domain: "*"}\n'
            "    action: deny\n"
            "    label: catch-all\n"
        )
        rules = load_rules(policy)
        assert len(rules) == 2
        assert rules[0].action == Action.ALLOW
        assert rules[0].label == "github read"
        assert rules[1].action == Action.DENY

    def test_load_empty_rules(self, tmp_path):
        policy = tmp_path / "policy.yaml"
        policy.write_text("rules: []\n")
        rules = load_rules(policy)
        assert rules == []

    def test_label_defaults_to_empty_string(self, tmp_path):
        policy = tmp_path / "policy.yaml"
        policy.write_text(
            "rules:\n"
            '  - match: {domain: "github.com"}\n'
            "    action: allow\n"
        )
        rules = load_rules(policy)
        assert rules[0].label == ""
