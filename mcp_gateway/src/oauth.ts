import { existsSync, mkdirSync, readFileSync, writeFileSync } from "fs";
import { homedir } from "os";
import { createHash, randomBytes } from "crypto";
import { createServer } from "http";
import { execFileSync, execFile } from "child_process";

const TOKEN_STORE_PATH = `${homedir()}/.agent-sandbox/oauth-tokens.json`;

interface TokenData {
  access_token: string;
  refresh_token?: string;
  expires_at: number;
  client_id: string;
  token_endpoint: string;
  server_url: string;
}

function loadTokenStore(): Record<string, TokenData> {
  if (!existsSync(TOKEN_STORE_PATH)) return {};
  return JSON.parse(readFileSync(TOKEN_STORE_PATH, "utf-8"));
}

function saveTokenStore(store: Record<string, TokenData>): void {
  const dir = TOKEN_STORE_PATH.substring(0, TOKEN_STORE_PATH.lastIndexOf("/"));
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  writeFileSync(TOKEN_STORE_PATH, JSON.stringify(store, null, 2));
}

export function getValidAccessToken(serverKey: string): string | null {
  const store = loadTokenStore();
  const token = store[serverKey];
  if (!token) return null;

  if (token.expires_at > Date.now() / 1000 + 60) {
    return token.access_token;
  }

  return refreshToken(serverKey, token);
}

function refreshToken(serverKey: string, token: TokenData): string | null {
  if (!token.refresh_token || !token.client_id || !token.token_endpoint) {
    return null;
  }

  try {
    const result = execFileSync("curl", [
      "-s", "-X", "POST", token.token_endpoint,
      "-d", `grant_type=refresh_token`,
      "-d", `refresh_token=${token.refresh_token}`,
      "-d", `client_id=${token.client_id}`,
    ], { encoding: "utf-8" });

    const data = JSON.parse(result);
    if (!data.access_token) return null;

    const store = loadTokenStore();
    store[serverKey] = {
      ...token,
      access_token: data.access_token,
      refresh_token: data.refresh_token ?? token.refresh_token,
      expires_at: Date.now() / 1000 + (data.expires_in ?? 3600),
    };
    saveTokenStore(store);

    console.error(`Token refreshed for '${serverKey}'`);
    return data.access_token;
  } catch (e) {
    console.error(`Token refresh failed for '${serverKey}': ${e}`);
    return null;
  }
}

export async function login(
  serverUrl: string,
  serverKey: string,
  oauthConfig?: { clientId?: string; callbackPort?: number }
): Promise<string> {
  const callbackPort = oauthConfig?.callbackPort ?? 9876;

  const metadata = await discoverMetadata(serverUrl);
  const authEndpoint = metadata.authorization_endpoint as string;
  const tokenEndpoint = metadata.token_endpoint as string;
  const registrationEndpoint = metadata.registration_endpoint as string | undefined;

  const redirectUri = `http://localhost:${callbackPort}/callback`;
  let clientId = oauthConfig?.clientId;

  if (!clientId) {
    const store = loadTokenStore();
    clientId = store[serverKey]?.client_id;
  }

  if (!clientId && registrationEndpoint) {
    clientId = await registerClient(registrationEndpoint, redirectUri);
  }

  if (!clientId) throw new Error(`No client_id for '${serverKey}'`);

  // PKCE
  const codeVerifier = randomBytes(48).toString("base64url");
  const codeChallenge = createHash("sha256")
    .update(codeVerifier)
    .digest("base64url");
  const state = randomBytes(24).toString("base64url");

  const params = new URLSearchParams({
    response_type: "code",
    client_id: clientId,
    redirect_uri: redirectUri,
    state,
    code_challenge: codeChallenge,
    code_challenge_method: "S256",
  });

  // Add scopes from OAuth metadata if available
  const scopes = metadata.scopes_supported as string[] | undefined;
  if (scopes && scopes.length > 0) {
    params.set("scope", scopes.join(" "));
  }

  const authUrl = `${authEndpoint}?${params}`;
  const code = await runCallbackServer(authUrl, state, callbackPort);

  const tokenResp = await fetch(tokenEndpoint, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      code,
      redirect_uri: redirectUri,
      client_id: clientId,
      code_verifier: codeVerifier,
    }),
  });
  const tokenData = await tokenResp.json() as Record<string, unknown>;

  if (!tokenData.access_token) {
    throw new Error(`Token exchange failed: ${JSON.stringify(tokenData)}`);
  }

  const store = loadTokenStore();
  store[serverKey] = {
    access_token: tokenData.access_token as string,
    refresh_token: tokenData.refresh_token as string | undefined,
    expires_at: Date.now() / 1000 + ((tokenData.expires_in as number) ?? 3600),
    client_id: clientId,
    token_endpoint: tokenEndpoint,
    server_url: serverUrl,
  };
  saveTokenStore(store);

  console.error(`OAuth login successful for '${serverKey}'`);
  return tokenData.access_token as string;
}

async function discoverMetadata(
  serverUrl: string
): Promise<Record<string, unknown>> {
  const url = new URL(serverUrl);
  const pathParts = url.pathname.replace(/\/$/, "").split("/");

  for (let i = pathParts.length; i >= 0; i--) {
    const base = pathParts.slice(0, i).join("/");
    const metaUrl = `${url.origin}${base}/.well-known/oauth-authorization-server`;
    try {
      const resp = await fetch(metaUrl, { redirect: "follow" });
      if (resp.ok) {
        console.error(`OAuth metadata found at ${metaUrl}`);
        return (await resp.json()) as Record<string, unknown>;
      }
    } catch {
      continue;
    }
  }
  throw new Error(`Could not discover OAuth metadata for ${serverUrl}`);
}

async function registerClient(
  endpoint: string,
  redirectUri: string
): Promise<string> {
  const resp = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      client_name: "agent-sandbox-gateway",
      redirect_uris: [redirectUri],
      grant_types: ["authorization_code", "refresh_token"],
      response_types: ["code"],
      token_endpoint_auth_method: "none",
    }),
  });
  const data = (await resp.json()) as { client_id: string };
  console.error(`Registered OAuth client: ${data.client_id}`);
  return data.client_id;
}

function runCallbackServer(
  authUrl: string,
  expectedState: string,
  port: number
): Promise<string> {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      server.close();
      reject(new Error("OAuth callback timeout (120s)"));
    }, 120000);

    const server = createServer((req, res) => {
      const url = new URL(req.url!, `http://localhost:${port}`);
      if (url.pathname !== "/callback") {
        res.writeHead(404).end();
        return;
      }

      const state = url.searchParams.get("state");
      const code = url.searchParams.get("code");
      const error = url.searchParams.get("error");

      if (error) {
        res.writeHead(200, { "Content-Type": "text/html" });
        res.end("<h1>Authorization failed</h1><p>You can close this tab.</p>");
        clearTimeout(timeout);
        server.close();
        reject(new Error(`OAuth error: ${error}`));
        return;
      }

      if (state !== expectedState) {
        res.writeHead(400, { "Content-Type": "text/html" });
        res.end("<h1>Invalid state</h1>");
        return;
      }

      res.writeHead(200, { "Content-Type": "text/html" });
      res.end("<h1>Authorization successful</h1><p>You can close this tab.</p>");
      clearTimeout(timeout);
      server.close();
      resolve(code!);
    });

    server.listen(port, "127.0.0.1", () => {
      console.error(`\nOpening browser for OAuth login:\n${authUrl}\n`);
      execFile("open", [authUrl], () => {});
    });
  });
}
