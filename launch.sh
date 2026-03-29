#!/bin/bash
set -euo pipefail

CLIENT_ID=${1:?Usage: launch.sh <client_id> <workspace_path>}
WORKSPACE=${2:?Usage: launch.sh <client_id> <workspace_path>}

CONFIG_DIR="${SANDBOX_CONFIG_DIR:-./config}/${CLIENT_ID}"
VAULT_DIR="${VAULT_DIR:-./vault}"
PROXY_PORT="${PROXY_PORT:-3128}"
GATEWAY_PORT="${GATEWAY_PORT:-3129}"

# Persistent storage for this client's Claude Code state
CLIENT_DIR="$(pwd)/clients/${CLIENT_ID}"
CLAUDE_DIR="${CLIENT_DIR}/.claude"

# Validate config exists
if [ ! -d "$CONFIG_DIR" ]; then
    echo "ERROR: config directory not found: $CONFIG_DIR" >&2
    exit 1
fi

# Verify proxy is running
if ! curl -s -o /dev/null --connect-timeout 2 http://127.0.0.1:$PROXY_PORT 2>/dev/null; then
    echo "ERROR: proxy not running on port $PROXY_PORT" >&2
    echo "Start it with: cd http_proxy && source .venv/bin/activate && CLIENT_ID=$CLIENT_ID VAULT_DIR=../vault HTTP_POLICY=../config/$CLIENT_ID/http_policy.yaml mitmdump -s addon.py -p $PROXY_PORT" >&2
    exit 1
fi

# Create persistent directories
mkdir -p "$CLAUDE_DIR"
LOCAL_DIR="${CLIENT_DIR}/.local"
mkdir -p "$LOCAL_DIR"

# Sync auth files from host only on first run (don't overwrite login state)
if [ ! -f "$CLIENT_DIR/.claude.json" ]; then
    cp "${HOME}/.claude.json" "$CLIENT_DIR/.claude.json" 2>/dev/null || true
fi
if [ ! -f "$CLAUDE_DIR/.credentials.json" ]; then
    cp "${HOME}/.claude/.credentials.json" "$CLAUDE_DIR/.credentials.json" 2>/dev/null || true
fi

# Generate .mcp.json for MCP Gateway connection (if gateway is running)
MCP_JSON_MOUNT=""
GATEWAY_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 http://127.0.0.1:$GATEWAY_PORT/sse 2>/dev/null || true)
if [ "$GATEWAY_STATUS" = "200" ]; then
    cat > "$CLIENT_DIR/.mcp.json" << MCPEOF
{
  "mcpServers": {
    "sandbox-gateway": {
      "type": "sse",
      "url": "http://host.docker.internal:${GATEWAY_PORT}/sse"
    }
  }
}
MCPEOF
    cp "$CLIENT_DIR/.mcp.json" "${WORKSPACE}/.mcp.json"
    echo "MCP Gateway: host.docker.internal:$GATEWAY_PORT"
else
    echo "MCP Gateway: not running (port $GATEWAY_PORT), skipping"
fi

# Resource limits
CPU_LIMIT="${CPU_LIMIT:-2}"
MEMORY_LIMIT="${MEMORY_LIMIT:-4g}"
PIDS_LIMIT="${PIDS_LIMIT:-256}"
TIMEOUT="${TIMEOUT:-3600}"  # 1 hour default

echo "Launching sandbox for client: $CLIENT_ID"
echo "Proxy: host.docker.internal:$PROXY_PORT"
echo "Workspace: $WORKSPACE"
echo "Client dir: $CLIENT_DIR"

docker run --rm -it \
    --name "sandbox-${CLIENT_ID}" \
    --add-host=host.docker.internal:host-gateway \
    --cap-add=NET_ADMIN \
    --read-only \
    --tmpfs /tmp:rw,nosuid,size=500m \
    --tmpfs /home/sandbox:rw,nosuid,size=500m \
    --tmpfs /run:rw,nosuid,size=10m \
    --cpus="$CPU_LIMIT" \
    --memory="$MEMORY_LIMIT" \
    --pids-limit="$PIDS_LIMIT" \
    -v "${WORKSPACE}:/workspace" \
    -v "${CLAUDE_DIR}:/home/sandbox/.claude" \
    -v "${CLIENT_DIR}/.claude.json:/home/sandbox/.claude.json" \
    -v "${LOCAL_DIR}:/home/sandbox/.local" \
    -v "${CONFIG_DIR}/CLAUDE.md:/workspace/CLAUDE.md:ro" \
    -e CLIENT_ID="${CLIENT_ID}" \
    -e PROXY_HOST="host.docker.internal" \
    -e PROXY_PORT="$PROXY_PORT" \
    -e HTTPS_PROXY="http://host.docker.internal:$PROXY_PORT" \
    -e HTTP_PROXY="http://host.docker.internal:$PROXY_PORT" \
    -e NO_PROXY="host.docker.internal,localhost,127.0.0.1" \
    -e no_proxy="host.docker.internal,localhost,127.0.0.1" \
    --stop-timeout=30 \
    sandbox-agent \
    timeout "$TIMEOUT" claude --dangerously-skip-permissions --continue ${VERBOSE:+--verbose} --debug
