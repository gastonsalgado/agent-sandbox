import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import { SSEClientTransport } from "@modelcontextprotocol/sdk/client/sse.js";
import type { Tool } from "@modelcontextprotocol/sdk/types.js";
import type { GatewayConfig, UpstreamConfig } from "./config.js";
import { getValidAccessToken, login } from "./oauth.js";

export class UpstreamManager {
  private clients = new Map<string, Client>();
  private toolMap = new Map<string, string>(); // tool name → upstream name
  private toolDefs = new Map<string, Tool>(); // tool name → definition

  async start(config: GatewayConfig): Promise<void> {
    for (const [name, upstream] of Object.entries(config.upstreams)) {
      try {
        await this.connectUpstream(name, upstream);
      } catch (e) {
        console.error(`Failed to connect upstream '${name}': ${e}`);
      }
    }
  }

  private async connectUpstream(
    name: string,
    config: UpstreamConfig
  ): Promise<void> {
    const headers = await this.resolveAuth(name, config);
    const url = new URL(config.url);

    let transport;
    if (config.type === "sse") {
      transport = new SSEClientTransport(url, {
        requestInit: headers ? { headers } : undefined,
      });
    } else {
      transport = new StreamableHTTPClientTransport(url, {
        requestInit: headers ? { headers } : undefined,
      });
    }

    const client = new Client({ name: "mcp-gateway", version: "0.1.0" });

    // Connect with timeout
    await Promise.race([
      client.connect(transport),
      new Promise((_, reject) =>
        setTimeout(() => reject(new Error("Connect timeout (30s)")), 30000)
      ),
    ]);

    this.clients.set(name, client);

    // Index tools
    const result = await client.listTools();
    for (const tool of result.tools) {
      this.toolMap.set(tool.name, name);
      this.toolDefs.set(tool.name, tool);
    }

    console.error(
      `Upstream '${name}' connected: ${result.tools.length} tools`
    );
  }

  getAllTools(): Tool[] {
    return Array.from(this.toolDefs.values());
  }

  async callTool(
    name: string,
    args: Record<string, unknown>
  ): Promise<{ content: Array<{ type: string; text: string }>; isError?: boolean }> {
    const upstreamName = this.toolMap.get(name);
    if (!upstreamName) {
      return {
        content: [{ type: "text", text: `Unknown tool: ${name}` }],
        isError: true,
      };
    }

    const client = this.clients.get(upstreamName)!;
    const result = await client.callTool({ name, arguments: args });
    // Normalize result to always have content array
    if ("content" in result) {
      return result as any;
    }
    return {
      content: [{ type: "text", text: JSON.stringify(result) }],
    };
  }

  private async resolveAuth(
    name: string,
    config: UpstreamConfig
  ): Promise<Record<string, string> | null> {
    const auth = config.auth;
    if (!auth) return null;

    if (auth.source === "env") {
      const envVar = auth.env_var!;
      const token = process.env[envVar];
      if (!token) {
        throw new Error(`Environment variable ${envVar} not set`);
      }
      return { Authorization: `Bearer ${token}` };
    }

    if (auth.source === "oauth") {
      let token = getValidAccessToken(name);
      if (!token) {
        console.error(`No valid token for '${name}', starting OAuth login...`);
        token = await login(config.url, name, auth.oauth);
      }
      return { Authorization: `Bearer ${token}` };
    }

    return null;
  }
}
