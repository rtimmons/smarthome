import { execFileSync } from "child_process";
import * as path from "path";

export type JsonObject = Record<string, any>;

export interface HomeAssistantConnectionOptions {
  host: string;
  server: string;
}

export const DEFAULT_HASS_HOST = "root@homeassistant.local";
export const DEFAULT_HASS_SERVER = "http://homeassistant.local:8123";
export const DEFAULT_HASS_SSH_IDENTITY = path.resolve(
  __dirname,
  "../../../../.ssh/id_ed25519_codex_smarthome"
);

export function getSshOptions(
  env: NodeJS.ProcessEnv = process.env
): string[] {
  return [
    "-i",
    env.HASS_SSH_IDENTITY ?? DEFAULT_HASS_SSH_IDENTITY,
    "-o",
    "IdentitiesOnly=yes",
    "-o",
    "BatchMode=yes",
    "-o",
    "ConnectTimeout=10",
    "-o",
    "StrictHostKeyChecking=no",
  ];
}

export function runCommand(
  command: string,
  args: string[],
  extraEnv?: NodeJS.ProcessEnv,
  input?: string
): string {
  try {
    return execFileSync(command, args, {
      encoding: "utf8",
      env: {
        ...process.env,
        ...extraEnv,
      },
      input,
      stdio: ["pipe", "pipe", "pipe"],
    }).trim();
  } catch (error) {
    const stderr =
      error &&
      typeof error === "object" &&
      "stderr" in error &&
      typeof error.stderr === "string"
        ? error.stderr.trim()
        : "";
    throw new Error(`${command} failed${stderr ? `: ${stderr}` : ""}`);
  }
}

export function runSsh(host: string, remoteCommand: string): string {
  return runCommand("ssh", [...getSshOptions(), host, remoteCommand]);
}

function normalizeClientId(clientId: string): string {
  return clientId.endsWith("/") ? clientId : `${clientId}/`;
}

export function selectOwnerRefreshToken(
  auth: JsonObject,
  preferredClientId: string
): JsonObject | undefined {
  const ownerUserIds = new Set(
    auth.data.users
      .filter((user: JsonObject) => user.is_owner)
      .map((user: JsonObject) => user.id)
  );
  const normalizedClientId = normalizeClientId(preferredClientId);
  const ownerTokens = auth.data.refresh_tokens.filter(
    (token: JsonObject) =>
      ownerUserIds.has(token.user_id) &&
      typeof token.token === "string" &&
      token.token.length > 0
  );

  return (
    ownerTokens.find(
      (token: JsonObject) => token.client_id === normalizedClientId
    ) ?? ownerTokens[0]
  );
}

export function getAccessToken(options: HomeAssistantConnectionOptions): string {
  if (process.env.HASS_TOKEN) {
    return process.env.HASS_TOKEN;
  }

  const auth = JSON.parse(runSsh(options.host, "cat /config/.storage/auth"));
  const refreshToken = selectOwnerRefreshToken(auth, options.server);

  if (!refreshToken) {
    throw new Error("Unable to locate an owner refresh token over SSH");
  }

  const clientId =
    typeof refreshToken.client_id === "string" && refreshToken.client_id.length > 0
      ? refreshToken.client_id
      : normalizeClientId(options.server);
  const body = [
    "grant_type=refresh_token",
    `client_id=${encodeURIComponent(clientId)}`,
    `refresh_token=${encodeURIComponent(refreshToken.token)}`,
  ].join("&");

  const response = JSON.parse(
    runCommand(
      "curl",
      [
        "-sS",
        "--max-time",
        "10",
        "-X",
        "POST",
        `${options.server}/auth/token`,
        "-H",
        "Content-Type: application/x-www-form-urlencoded",
        "--data-binary",
        "@-",
      ],
      undefined,
      body
    )
  );

  if (!response.access_token) {
    throw new Error("Failed to exchange refresh token for an access token");
  }

  return response.access_token as string;
}

function websocketUrl(server: string): string {
  if (server.startsWith("https://")) {
    return `wss://${server.slice("https://".length)}/api/websocket`;
  }
  if (server.startsWith("http://")) {
    return `ws://${server.slice("http://".length)}/api/websocket`;
  }
  throw new Error(`Unsupported Home Assistant server URL: ${server}`);
}

function authorizationHeaders(accessToken: string): string {
  return [
    `Authorization: Bearer ${accessToken}`,
    "Content-Type: application/json",
    "",
  ].join("\n");
}

export function callHomeAssistantWs<T>(
  options: HomeAssistantConnectionOptions,
  accessToken: string,
  payload: Record<string, any>,
  timeoutMs = 10000
): Promise<T> {
  return new Promise((resolve, reject) => {
    const socket = new WebSocket(websocketUrl(options.server));
    let settled = false;
    const timeout = setTimeout(() => {
      finish(() => reject(new Error("Home Assistant websocket call timed out")));
    }, timeoutMs);

    const finish = (fn: () => void) => {
      if (settled) {
        return;
      }
      settled = true;
      clearTimeout(timeout);
      fn();
      socket.close();
    };

    socket.addEventListener("message", (event: MessageEvent) => {
      const message = JSON.parse(String(event.data));

      if (message.type === "auth_required") {
        socket.send(
          JSON.stringify({
            type: "auth",
            access_token: accessToken,
          })
        );
        return;
      }

      if (message.type === "auth_invalid") {
        finish(() => reject(new Error("Home Assistant websocket authentication failed")));
        return;
      }

      if (message.type === "auth_ok") {
        socket.send(
          JSON.stringify({
            id: 1,
            ...payload,
          })
        );
        return;
      }

      if (message.id === 1) {
        if (message.success) {
          finish(() => resolve(message.result as T));
          return;
        }

        finish(() =>
          reject(
            new Error(
              `Home Assistant websocket call failed: ${JSON.stringify(
                message.error ?? message
              )}`
            )
          )
        );
      }
    });

    socket.addEventListener("error", () => {
      finish(() => reject(new Error("Home Assistant websocket connection failed")));
    });
  });
}

export function fetchStates(
  options: HomeAssistantConnectionOptions,
  accessToken: string
): JsonObject[] {
  return JSON.parse(
    runCommand(
      "curl",
      [
        "-sS",
        "--max-time",
        "10",
        `${options.server}/api/states`,
        "-H",
        "@-",
      ],
      undefined,
      authorizationHeaders(accessToken)
    )
  ) as JsonObject[];
}

export function fetchState(
  options: HomeAssistantConnectionOptions,
  accessToken: string,
  entityId: string
): JsonObject | null {
  const response = runCommand(
    "curl",
    [
      "-sS",
      "--max-time",
      "10",
      "-o",
      "-",
      "-w",
      "\n%{http_code}",
      `${options.server}/api/states/${encodeURIComponent(entityId)}`,
      "-H",
      "@-",
    ],
    undefined,
    authorizationHeaders(accessToken)
  );
  const splitIndex = response.lastIndexOf("\n");
  const body = splitIndex >= 0 ? response.slice(0, splitIndex) : response;
  const statusCode = Number(splitIndex >= 0 ? response.slice(splitIndex + 1) : "0");

  if (statusCode === 404) {
    return null;
  }

  if (statusCode < 200 || statusCode >= 300) {
    throw new Error(`Failed to fetch ${entityId}: HTTP ${statusCode} ${body}`);
  }

  return JSON.parse(body) as JsonObject;
}

export function callService(
  options: HomeAssistantConnectionOptions,
  accessToken: string,
  domain: string,
  service: string,
  data: Record<string, any>
): JsonObject[] {
  return JSON.parse(
    runCommand(
      "curl",
      [
        "-sS",
        "--max-time",
        "10",
        "-X",
        "POST",
        `${options.server}/api/services/${domain}/${service}`,
        "-H",
        "@-",
        "--data-binary",
        JSON.stringify(data),
      ],
      undefined,
      authorizationHeaders(accessToken)
    )
  ) as JsonObject[];
}
