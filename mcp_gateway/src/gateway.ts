import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import {
  ListToolsRequestSchema,
  CallToolRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import type { Rule } from "./policy.js";
import { Action, evaluate } from "./policy.js";
import { approvalService } from "./approval.js";
import { log as auditLog } from "./audit.js";
import type { UpstreamManager } from "./upstream.js";

const CLIENT_ID = process.env.CLIENT_ID ?? "default";

export function createGateway(
  upstream: UpstreamManager,
  rules: Rule[]
): Server {
  const server = new Server(
    { name: "mcp-gateway", version: "0.1.0" },
    { capabilities: { tools: { listChanged: true } } }
  );

  server.setRequestHandler(ListToolsRequestSchema, async () => {
    const allTools = upstream.getAllTools();
    const allowed = allTools.filter((tool) => {
      const decision = evaluate({ tool: tool.name }, rules);
      return decision.action !== Action.DENY;
    });
    return { tools: allowed };
  });

  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;
    const fields = { tool: name };
    const decision = evaluate(fields, rules);

    if (decision.action === Action.DENY) {
      auditLog({
        action: "DENY",
        client_id: CLIENT_ID,
        reason: decision.reason,
        fields,
      });
      return {
        content: [{ type: "text" as const, text: `Blocked: ${decision.reason}` }],
        isError: true,
      };
    }

    if (decision.action === Action.APPROVAL) {
      const detail = `${name}(${summarize(args)})`;
      const approved = await approvalService.requestApproval(
        decision.reason,
        detail
      );
      if (!approved) {
        auditLog({
          action: "DENIED",
          client_id: CLIENT_ID,
          reason: decision.reason,
          fields,
        });
        return {
          content: [
            { type: "text" as const, text: `Denied by operator: ${decision.reason}` },
          ],
          isError: true,
        };
      }
      auditLog({
        action: "APPROVED",
        client_id: CLIENT_ID,
        reason: decision.reason,
        fields,
      });
    } else {
      auditLog({
        action: "ALLOW",
        client_id: CLIENT_ID,
        reason: decision.reason,
        fields,
      });
    }

    return await upstream.callTool(name, args ?? {});
  });

  return server;
}

function summarize(
  args: Record<string, unknown> | undefined,
  maxLen: number = 100
): string {
  if (!args) return "";
  const parts = Object.entries(args).map(([k, v]) => `${k}=${v}`);
  const text = parts.join(", ");
  return text.length > maxLen ? text.slice(0, maxLen) + "..." : text;
}
