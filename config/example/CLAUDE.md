# Sandboxed Agent

You are running in an isolated sandbox container. Your network access is mediated by a proxy.

## Rules
- Use git, curl, and other CLIs directly for READ operations
- For WRITE operations (push, deploy, update), the proxy will request human approval
- If a CLI command is blocked, check the error message for the reason
- Use MCP tools for operations that need structured input and approval
- Never try to bypass proxy restrictions or access credentials directly
- All operations are logged and audited
