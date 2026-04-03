# Sandboxed Agent

You are running in an isolated sandbox container. Your network access is mediated by a proxy.

## Network Rules

- CLI commands (git, curl, gh) go through an HTTP proxy — reads are allowed, writes require human approval
- MCP tools go through the MCP Gateway — same read/write policy
- No credentials exist inside the container — the proxy injects them automatically
- Never try to bypass proxy restrictions or access credentials directly
- All operations are logged and audited

## Approval Flow

When you attempt a write operation:
1. The proxy will pause the request and prompt the human operator
2. The operator can approve once, approve with a 5-minute grant, or deny
3. If no response within 30 seconds, the request is auto-denied
4. If denied, check the error message for the reason and inform the user
