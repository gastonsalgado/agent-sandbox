FROM ubuntu:24.04

# CLIs for agent operations
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    git \
    curl \
    wget \
    socat \
    jq \
    python3 \
    python3-pip \
    python3-venv \
    sudo \
    gosu \
    iptables \
    iproute2 \
    unzip \
    gnupg2 \
    apt-transport-https \
    && rm -rf /var/lib/apt/lists/*

# Node.js LTS (required by Claude Code)
RUN curl -fsSL https://deb.nodesource.com/setup_24.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Google Cloud SDK
RUN echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" \
    > /etc/apt/sources.list.d/google-cloud-sdk.list \
    && curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg \
    | gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg \
    && apt-get update && apt-get install -y --no-install-recommends google-cloud-cli \
    && rm -rf /var/lib/apt/lists/*

# AWS CLI v2
RUN ARCH=$(dpkg --print-architecture) \
    && if [ "$ARCH" = "amd64" ]; then AWS_ARCH="x86_64"; else AWS_ARCH="aarch64"; fi \
    && curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-${AWS_ARCH}.zip" -o /tmp/aws.zip \
    && unzip -q /tmp/aws.zip -d /tmp && /tmp/aws/install && rm -rf /tmp/aws*

# GitHub CLI
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
    | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
    > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/*

# Claude Code (native installer)
# Install as sandbox user, then relocate to /opt so tmpfs on /home doesn't hide it
RUN useradd -m -s /bin/bash sandbox \
    && su sandbox -c "curl -fsSL https://claude.ai/install.sh | bash" \
    && mkdir -p /opt/claude-code \
    && cp -a /home/sandbox/.local/share/claude/. /opt/claude-code/ \
    && ln -sf /opt/claude-code/versions/$(ls /opt/claude-code/versions/) /usr/local/bin/claude

# mitmproxy CA certificate (trust proxy's TLS)
COPY mitmproxy-ca-cert.pem /usr/local/share/ca-certificates/mitmproxy.crt
RUN update-ca-certificates

# MCP relay (stdio -> unix socket bridge)
COPY mcp-relay.py /usr/local/bin/mcp-relay
RUN chmod +x /usr/local/bin/mcp-relay

# Firewall setup script (runs as root before dropping to sandbox user)
COPY init-firewall.sh /usr/local/bin/init-firewall.sh
RUN chmod +x /usr/local/bin/init-firewall.sh

# Proxy env vars
ENV NODE_EXTRA_CA_CERTS=/usr/local/share/ca-certificates/mitmproxy.crt

# Disable gcloud file logging (tmpfs has limited space)
ENV CLOUDSDK_CORE_DISABLE_FILE_LOGGING=1
# Tell gcloud and Python requests to trust the mitmproxy CA
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
ENV CLOUDSDK_CORE_CUSTOM_CA_CERTS_FILE=/etc/ssl/certs/ca-certificates.crt
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

# Dummy credentials — CLIs need these to attempt requests.
# The proxy intercepts and replaces with real credentials from the vault.
ENV GITHUB_TOKEN=dummy-proxy-will-replace
ENV GH_TOKEN=dummy-proxy-will-replace
ENV CLOUDSDK_AUTH_ACCESS_TOKEN=dummy-proxy-will-replace
ENV AWS_ACCESS_KEY_ID=dummy-proxy-will-replace
ENV AWS_SECRET_ACCESS_KEY=dummy-proxy-will-replace
ENV AWS_DEFAULT_REGION=us-east-1
ENV SLACK_TOKEN=dummy-proxy-will-replace

# Sudo allowed for everything EXCEPT network/firewall tools
RUN echo "sandbox ALL=(ALL) NOPASSWD:ALL, !/usr/sbin/iptables, !/usr/sbin/ip6tables, !/usr/sbin/ipset, !/usr/sbin/ip" \
       > /etc/sudoers.d/sandbox \
    && chmod 0440 /etc/sudoers.d/sandbox
ENV HOME=/home/sandbox
ENV PATH="/home/sandbox/.local/bin:$PATH"

# Force git to HTTPS (prevents SSH which bypasses proxy)
RUN git config --system url."https://github.com/".insteadOf "git@github.com:" \
    && git config --system url."https://github.com/".insteadOf "ssh://git@github.com/"

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /workspace
# Entrypoint runs as root (for iptables), then drops to sandbox user
ENTRYPOINT ["/entrypoint.sh"]
