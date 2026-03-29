#!/bin/bash
set -euo pipefail

# Run firewall setup as root
/usr/local/bin/init-firewall.sh

# Create dirs that CLIs expect to write to (tmpfs starts empty)
mkdir -p /home/sandbox/.config/gcloud /home/sandbox/.aws

# Seed Claude Code binary into persistent .local if not present
if [ ! -f /home/sandbox/.local/bin/claude ]; then
    cp -a /opt/claude-code/. /home/sandbox/.local/share/claude/ 2>/dev/null || true
    mkdir -p /home/sandbox/.local/bin
    ln -sf /home/sandbox/.local/share/claude/versions/$(ls /opt/claude-code/versions/) /home/sandbox/.local/bin/claude
fi

# Fix ownership of home and workspace
chown -R sandbox:sandbox /home/sandbox 2>/dev/null || true
chown -R sandbox:sandbox /workspace 2>/dev/null || true

# Drop to sandbox user and execute command
exec gosu sandbox "$@"
