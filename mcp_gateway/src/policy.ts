import type { RuleConfig } from "./config.js";

export enum Action {
  ALLOW = "allow",
  DENY = "deny",
  APPROVAL = "approval",
}

export interface Decision {
  action: Action;
  reason: string;
}

export interface Rule {
  match: Record<string, string>;
  action: Action;
  label: string;
}

export function parseRules(configs: RuleConfig[]): Rule[] {
  return configs.map((c) => ({
    match: c.match,
    action: c.action as Action,
    label: c.label ?? "",
  }));
}

export function evaluate(
  fields: Record<string, string>,
  rules: Rule[]
): Decision {
  for (const rule of rules) {
    if (matches(fields, rule.match)) {
      return { action: rule.action, reason: rule.label || JSON.stringify(rule.match) };
    }
  }
  return { action: Action.DENY, reason: "no matching rule" };
}

function matches(
  fields: Record<string, string>,
  match: Record<string, string>
): boolean {
  for (const [key, pattern] of Object.entries(match)) {
    if (pattern === "*") continue;

    if (key.endsWith("_contains")) {
      const actualKey = key.slice(0, -"_contains".length);
      const value = fields[actualKey] ?? "";
      if (!value.includes(pattern)) return false;
    } else {
      const value = fields[key] ?? "";
      if (value !== pattern) return false;
    }
  }
  return true;
}
