#!/bin/bash
set -euo pipefail

# Firewall for sandbox container:
# - Allow DNS (needed for resolution)
# - Allow localhost (proxy bridge, MCP relay)
# - Allow traffic to proxy port on host (credential injection + approval)
# - Allow all external internet traffic (agent needs free access)
# - Block access to host services and local network (protect host)

PROXY_HOST="${PROXY_HOST:-host.docker.internal}"
PROXY_PORT="${PROXY_PORT:-3128}"

# Detect host IP from default route
HOST_IP=$(ip route | grep default | awk '{print $3}')
if [ -z "$HOST_IP" ]; then
    echo "ERROR: cannot detect host IP" >&2
    exit 1
fi

echo "Host IP: $HOST_IP"
echo "Proxy: $PROXY_HOST:$PROXY_PORT"

# Preserve Docker DNS rules
DOCKER_DNS_RULES=$(iptables-save -t nat | grep "127\.0\.0\.11" || true)

# Flush all rules
iptables -F
iptables -X
iptables -t nat -F
iptables -t nat -X

# Restore Docker DNS
if [ -n "$DOCKER_DNS_RULES" ]; then
    iptables -t nat -N DOCKER_OUTPUT 2>/dev/null || true
    iptables -t nat -N DOCKER_POSTROUTING 2>/dev/null || true
    echo "$DOCKER_DNS_RULES" | xargs -L 1 iptables -t nat
fi

# Default policies: drop everything, then allow selectively
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT DROP

# Allow established connections
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# Allow localhost (socat bridge, mcp-relay)
iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT

# Allow DNS (UDP + TCP port 53)
iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
iptables -A INPUT -p udp --sport 53 -j ACCEPT
iptables -A OUTPUT -p tcp --dport 53 -j ACCEPT

# Allow proxy on host (credential injection + approval)
iptables -A OUTPUT -d "$HOST_IP" -p tcp --dport "$PROXY_PORT" -j ACCEPT

# Block everything else to the host
iptables -A OUTPUT -d "$HOST_IP" -j REJECT --reject-with icmp-port-unreachable

# Block private networks (protect LAN)
iptables -A OUTPUT -d 10.0.0.0/8 -j REJECT --reject-with icmp-port-unreachable
iptables -A OUTPUT -d 172.16.0.0/12 -j REJECT --reject-with icmp-port-unreachable
iptables -A OUTPUT -d 192.168.0.0/16 -j REJECT --reject-with icmp-port-unreachable
iptables -A OUTPUT -d 169.254.0.0/16 -j REJECT --reject-with icmp-port-unreachable

# Allow all other outbound traffic (internet)
iptables -A OUTPUT -j ACCEPT

echo "Firewall configured: proxy=$HOST_IP:$PROXY_PORT, internet=open, host/LAN=blocked"
