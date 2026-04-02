import { readFileSync } from "fs";
import { parse } from "yaml";

export interface AuthConfig {
  source: "env" | "oauth";
  env_var?: string;
  oauth?: {
    clientId?: string;
    callbackPort?: number;
  };
}

export interface UpstreamConfig {
  type: "http" | "sse";
  url: string;
  auth?: AuthConfig;
}

export interface RuleConfig {
  match: Record<string, string>;
  action: "allow" | "deny" | "approval";
  label?: string;
}

export interface GatewayConfig {
  upstreams: Record<string, UpstreamConfig>;
  rules: RuleConfig[];
}

export function loadConfig(path: string): GatewayConfig {
  const content = readFileSync(path, "utf-8");
  const data = parse(content) as GatewayConfig;

  if (!data.upstreams) data.upstreams = {};
  if (!data.rules) data.rules = [];

  return data;
}
