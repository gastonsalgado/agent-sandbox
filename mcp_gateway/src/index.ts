import express from "express";
import { randomUUID } from "crypto";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { SSEServerTransport } from "@modelcontextprotocol/sdk/server/sse.js";
import { loadConfig } from "./config.js";
import { parseRules } from "./policy.js";
import { UpstreamManager } from "./upstream.js";
import { createGateway } from "./gateway.js";

const MCP_POLICY = process.env.MCP_POLICY ?? "/etc/sandbox/mcp_policy.yaml";
const CLIENT_ID = process.env.CLIENT_ID ?? "default";
const GATEWAY_PORT = parseInt(process.env.GATEWAY_PORT ?? "3129");

async function main() {
  const config = loadConfig(MCP_POLICY);
  const rules = parseRules(config.rules);
  console.error(`Loaded ${rules.length} policy rules`);

  const upstream = new UpstreamManager();
  await upstream.start(config);

  const tools = upstream.getAllTools();
  console.error(`Total tools from upstreams: ${tools.length}`);

  const app = express();
  app.use(express.json({ type: "application/json" }));

  // ── Streamable HTTP transport (/mcp) ──
  const httpTransports = new Map<string, StreamableHTTPServerTransport>();

  app.all("/mcp", async (req, res) => {
    const sessionId = req.headers["mcp-session-id"] as string | undefined;

    if (req.method === "GET" || (req.method === "POST" && !sessionId)) {
      const transport = new StreamableHTTPServerTransport({
        sessionIdGenerator: () => randomUUID(),
      });
      const server = createGateway(upstream, rules);
      await server.connect(transport);

      if (transport.sessionId) {
        httpTransports.set(transport.sessionId, transport);
        transport.onclose = () => {
          if (transport.sessionId) httpTransports.delete(transport.sessionId);
        };
      }
      await transport.handleRequest(req, res, req.body);
    } else if (sessionId && httpTransports.has(sessionId)) {
      await httpTransports.get(sessionId)!.handleRequest(req, res, req.body);
    } else {
      res.status(400).json({
        jsonrpc: "2.0",
        error: { code: -32600, message: "Invalid or missing session" },
      });
    }
  });

  // ── SSE transport (/sse + /messages) ──
  const sseTransports = new Map<string, SSEServerTransport>();

  app.get("/sse", async (req, res) => {
    const transport = new SSEServerTransport("/messages", res);
    const server = createGateway(upstream, rules);

    sseTransports.set(transport.sessionId, transport);
    transport.onclose = () => sseTransports.delete(transport.sessionId);

    await server.connect(transport);
  });

  app.post("/messages", async (req, res) => {
    const sessionId = req.query.sessionId as string;
    const transport = sseTransports.get(sessionId);
    if (!transport) {
      res.status(404).json({ error: "Session not found" });
      return;
    }
    await transport.handlePostMessage(req, res, req.body);
  });

  app.listen(GATEWAY_PORT, "127.0.0.1", () => {
    console.error(
      `MCP Gateway listening on http://127.0.0.1:${GATEWAY_PORT}`
    );
    console.error(`  Streamable HTTP: /mcp`);
    console.error(`  SSE: /sse`);
  });
}

main().catch((e) => {
  console.error(`Gateway failed: ${e}`);
  process.exit(1);
});
