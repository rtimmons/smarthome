#!/usr/bin/env node

import * as fs from "fs";
import * as os from "os";
import * as path from "path";
import { execFileSync } from "child_process";

import { scenes } from "../scenes";
import { generateFastSceneCalls, generateSceneEntities } from "../scene-generation";

declare const WebSocket: any;

type JsonObject = Record<string, any>;

interface Options {
  host: string;
  server: string;
  outputDir?: string;
  sceneIds: string[];
  logLines: number;
}

interface CacheEntry<T> {
  key: {
    nodeId: number;
    commandClass?: number;
    endpoint?: number;
    property?: string | number;
    propertyKey?: string | number;
  };
  value: T;
  timestamp?: number;
}

interface NodeInfo {
  nodeId: number;
  deviceId?: string;
  name?: string;
  model?: string;
  manufacturer?: string;
  entityIds: string[];
}

interface RampPlanItem {
  nodeId: number;
  deviceId: string;
  parameter: string;
  label: string;
  endpoint: number;
  currentValue: number;
  targetValue: number;
  entityIds: string[];
  deviceName: string;
  model?: string;
  manufacturer?: string;
  reason: string;
}

interface SceneSummary {
  id: string;
  entityCount: number;
  groupedCallCount: number;
  calls: Array<{
    service: string;
    entityCount: number;
    data?: Record<string, any>;
  }>;
}

const SSH_OPTIONS = [
  "-o",
  "BatchMode=yes",
  "-o",
  "StrictHostKeyChecking=no",
];

function parseArgs(argv: string[]): Options {
  const options: Options = {
    host: "root@homeassistant.local",
    server: "http://homeassistant.local:8123",
    sceneIds: [],
    logLines: 400,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];

    switch (arg) {
      case "--host":
        options.host = argv[++index];
        break;
      case "--server":
        options.server = argv[++index];
        break;
      case "--output-dir":
        options.outputDir = argv[++index];
        break;
      case "--scene":
        options.sceneIds.push(argv[++index]);
        break;
      case "--log-lines":
        options.logLines = Number(argv[++index]);
        break;
      default:
        throw new Error(`Unknown argument: ${arg}`);
    }
  }

  return options;
}

function ensureOutputDir(outputDir?: string): string {
  const resolved =
    outputDir ??
    path.join(
      os.tmpdir(),
      `zwave-scene-tools-${new Date().toISOString().replace(/[:.]/g, "-")}`
    );
  fs.mkdirSync(resolved, { recursive: true });
  return resolved;
}

function runCommand(
  command: string,
  args: string[],
  extraEnv?: NodeJS.ProcessEnv
): string {
  return execFileSync(command, args, {
    encoding: "utf8",
    env: {
      ...process.env,
      ...extraEnv,
    },
  }).trim();
}

function runSsh(host: string, remoteCommand: string): string {
  return runCommand("ssh", [...SSH_OPTIONS, host, remoteCommand]);
}

function scpFromRemote(host: string, remotePath: string, localPath: string) {
  execFileSync("scp", [...SSH_OPTIONS, `${host}:${remotePath}`, localPath], {
    stdio: "inherit",
  });
}

function fetchLiveArtifacts(options: Options, outputDir: string) {
  const valuesRemote = runSsh(
    options.host,
    "ls /addon_configs/core_zwave_js/cache/*.values.jsonl | head -n 1"
  );
  const metadataRemote = runSsh(
    options.host,
    "ls /addon_configs/core_zwave_js/cache/*.metadata.jsonl | head -n 1"
  );

  const files = [
    {
      remote: "/config/.storage/core.device_registry",
      local: path.join(outputDir, "core.device_registry.json"),
    },
    {
      remote: "/config/.storage/core.entity_registry",
      local: path.join(outputDir, "core.entity_registry.json"),
    },
    {
      remote: valuesRemote,
      local: path.join(outputDir, path.basename(valuesRemote)),
    },
    {
      remote: metadataRemote,
      local: path.join(outputDir, path.basename(metadataRemote)),
    },
  ];

  for (const file of files) {
    scpFromRemote(options.host, file.remote, file.local);
  }

  fs.writeFileSync(
    path.join(outputDir, "zwave.log"),
    runSsh(options.host, `ha apps logs core_zwave_js | tail -n ${options.logLines}`),
    "utf8"
  );
  fs.writeFileSync(
    path.join(outputDir, "core.log"),
    runSsh(options.host, `ha core logs | tail -n ${options.logLines}`),
    "utf8"
  );

  return {
    deviceRegistryPath: files[0].local,
    entityRegistryPath: files[1].local,
    valuesPath: files[2].local,
    metadataPath: files[3].local,
    zwaveLogPath: path.join(outputDir, "zwave.log"),
  };
}

function loadJson<T>(filePath: string): T {
  return JSON.parse(fs.readFileSync(filePath, "utf8")) as T;
}

function loadJsonl<T>(filePath: string): CacheEntry<T>[] {
  return fs
    .readFileSync(filePath, "utf8")
    .split("\n")
    .filter(Boolean)
    .map((line) => {
      const parsed = JSON.parse(line);
      return {
        key: JSON.parse(parsed.k),
        value: parsed.v as T,
        timestamp: parsed.ts,
      };
    });
}

function extractNodeId(identifiers: string[][]): number | undefined {
  for (const identifier of identifiers) {
    if (identifier[0] !== "zwave_js") {
      continue;
    }

    const match = identifier[1]?.match(/-(\d+)(?:-|$)/);
    if (match) {
      return Number(match[1]);
    }
  }

  return undefined;
}

function buildNodeMap(deviceRegistry: JsonObject, entityRegistry: JsonObject): Map<number, NodeInfo> {
  const nodes = new Map<number, NodeInfo>();
  const deviceById = new Map<string, JsonObject>();

  for (const device of deviceRegistry.data.devices as JsonObject[]) {
    deviceById.set(device.id, device);
    const nodeId = extractNodeId(device.identifiers ?? []);
    if (nodeId === undefined) {
      continue;
    }

    nodes.set(nodeId, {
      nodeId,
      deviceId: device.id,
      name: device.name ?? device.name_by_user ?? `Node ${nodeId}`,
      model: device.model ?? undefined,
      manufacturer: device.manufacturer ?? undefined,
      entityIds: [],
    });
  }

  for (const entity of entityRegistry.data.entities as JsonObject[]) {
    const device = deviceById.get(entity.device_id);
    if (!device) {
      continue;
    }

    const nodeId = extractNodeId(device.identifiers ?? []);
    if (nodeId === undefined) {
      continue;
    }

    const node = nodes.get(nodeId);
    if (node) {
      node.entityIds.push(entity.entity_id);
    }
  }

  for (const node of nodes.values()) {
    node.entityIds.sort();
  }

  return nodes;
}

function normalizeServerClientId(server: string): string {
  return server.endsWith("/") ? server : `${server}/`;
}

function getAccessToken(options: Options): string {
  if (process.env.HASS_TOKEN) {
    return process.env.HASS_TOKEN;
  }

  const auth = JSON.parse(runSsh(options.host, "cat /config/.storage/auth"));
  const ownerUserIds = new Set(
    auth.data.users
      .filter((user: JsonObject) => user.is_owner)
      .map((user: JsonObject) => user.id)
  );
  const preferredClientId = normalizeServerClientId(options.server);
  const refreshToken = auth.data.refresh_tokens.find(
    (token: JsonObject) =>
      ownerUserIds.has(token.user_id) &&
      typeof token.token === "string" &&
      token.token.length > 0 &&
      (!token.client_id || token.client_id === preferredClientId)
  ) ??
    auth.data.refresh_tokens.find(
      (token: JsonObject) =>
        ownerUserIds.has(token.user_id) &&
        typeof token.token === "string" &&
        token.token.length > 0
    );

  if (!refreshToken) {
    throw new Error("Unable to locate an owner refresh token over SSH");
  }

  const body = [
    `grant_type=refresh_token`,
    `client_id=${encodeURIComponent(preferredClientId)}`,
    `refresh_token=${encodeURIComponent(refreshToken.token)}`,
  ].join("&");

  const response = JSON.parse(
    runCommand("curl", [
      "-sS",
      "-X",
      "POST",
      `${options.server}/auth/token`,
      "-H",
      "Content-Type: application/x-www-form-urlencoded",
      "--data",
      body,
    ])
  );

  if (!response.access_token) {
    throw new Error("Failed to exchange refresh token for an access token");
  }

  return response.access_token as string;
}

function hassCli(options: Options, accessToken: string, ...args: string[]): string {
  return runCommand("hass-cli", args, {
    HASS_SERVER: options.server,
    HASS_TOKEN: accessToken,
  });
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

function callHomeAssistantWs<T>(
  options: Options,
  accessToken: string,
  payload: Record<string, any>
): Promise<T> {
  return new Promise((resolve, reject) => {
    const socket = new WebSocket(websocketUrl(options.server));
    let settled = false;

    const finish = (fn: () => void) => {
      if (settled) {
        return;
      }
      settled = true;
      fn();
      socket.close();
    };

    socket.addEventListener("message", (event: any) => {
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

function determineTargetValue(metadata: JsonObject, currentValue: unknown): {
  targetValue: number;
  reason: string;
} | null {
  const label = String(metadata.label ?? "");
  if (typeof currentValue !== "number") {
    return null;
  }

  if (/Ramp Rate/i.test(label) && metadata.min === 0) {
    return {
      targetValue: 0,
      reason: "instant ramp",
    };
  }

  if (/Transition Time/i.test(label) && metadata.min === 0) {
    return {
      targetValue: 0,
      reason: "instant transition",
    };
  }

  if (/Dimming Rate/i.test(label)) {
    const targetValue =
      typeof metadata.default === "number"
        ? metadata.default
        : typeof metadata.min === "number"
          ? metadata.min
          : 1;
    return {
      targetValue,
      reason: "fastest dimming rate",
    };
  }

  if (
    label === "Dim Rate" &&
    metadata.states &&
    metadata.states["0"] === "Dim Quickly"
  ) {
    return {
      targetValue: 0,
      reason: "quick dim rate",
    };
  }

  return null;
}

function buildRampPlan(
  valuesEntries: CacheEntry<unknown>[],
  metadataEntries: CacheEntry<JsonObject>[],
  nodeMap: Map<number, NodeInfo>
): RampPlanItem[] {
  const metadataByKey = new Map(
    metadataEntries.map((entry) => [JSON.stringify(entry.key), entry.value])
  );

  const pending: RampPlanItem[] = [];
  const seen = new Set<string>();

  for (const entry of valuesEntries) {
    const metadata = metadataByKey.get(JSON.stringify(entry.key));
    if (!metadata?.writeable) {
      continue;
    }

    const target = determineTargetValue(metadata, entry.value);
    if (!target) {
      continue;
    }

    const currentValue = entry.value as number;
    if (currentValue === target.targetValue) {
      continue;
    }

    const node = nodeMap.get(entry.key.nodeId);
    if (!node?.deviceId) {
      continue;
    }

    const signature = `${entry.key.nodeId}:${entry.key.endpoint ?? 0}:${String(
      entry.key.property
    )}:${target.targetValue}`;
    if (seen.has(signature)) {
      continue;
    }
    seen.add(signature);

    pending.push({
      nodeId: entry.key.nodeId,
      deviceId: node.deviceId,
      parameter: String(entry.key.property),
      label: String(metadata.label ?? entry.key.property),
      endpoint: entry.key.endpoint ?? 0,
      currentValue,
      targetValue: target.targetValue,
      entityIds: node.entityIds,
      deviceName: node.name ?? `Node ${entry.key.nodeId}`,
      manufacturer: node.manufacturer,
      model: node.model,
      reason: target.reason,
    });
  }

  return pending.sort((left, right) => {
    if (left.nodeId !== right.nodeId) {
      return left.nodeId - right.nodeId;
    }
    return Number(left.parameter) - Number(right.parameter);
  });
}

function buildSceneSummaries(sceneIds: string[]): SceneSummary[] {
  const ids = sceneIds.length > 0 ? sceneIds : Object.keys(scenes);

  return ids.map((sceneId) => {
    const scene = scenes[sceneId];
    if (!scene) {
      throw new Error(`Unknown scene: ${sceneId}`);
    }

    const entities = generateSceneEntities(scene);
    const calls = generateFastSceneCalls(scene);

    return {
      id: sceneId,
      entityCount: Object.keys(entities).length,
      groupedCallCount: calls.length,
      calls: calls.map((call) => ({
        service: call.service,
        entityCount: call.target.entity_id.length,
        ...(call.data && { data: call.data }),
      })),
    };
  });
}

function extractSuspiciousLogs(logText: string): string[] {
  return logText
    .split("\n")
    .filter((line) =>
      /(failed to decode|nonce without an active transaction|Supervision|No route|timed out|jammed)/i.test(
        line
      )
    )
    .slice(-40);
}

function loadArtifacts(artifactPaths: ReturnType<typeof fetchLiveArtifacts>) {
  const deviceRegistry = loadJson<JsonObject>(artifactPaths.deviceRegistryPath);
  const entityRegistry = loadJson<JsonObject>(artifactPaths.entityRegistryPath);
  const valuesEntries = loadJsonl<unknown>(artifactPaths.valuesPath);
  const metadataEntries = loadJsonl<JsonObject>(artifactPaths.metadataPath);

  return {
    deviceRegistry,
    entityRegistry,
    valuesEntries,
    metadataEntries,
    zwaveLog: fs.readFileSync(artifactPaths.zwaveLogPath, "utf8"),
  };
}

function writeJson(filePath: string, value: unknown) {
  fs.writeFileSync(filePath, JSON.stringify(value, null, 2), "utf8");
}

async function diagnose(options: Options) {
  const outputDir = ensureOutputDir(options.outputDir);
  const artifactPaths = fetchLiveArtifacts(options, outputDir);
  const artifacts = loadArtifacts(artifactPaths);
  const nodeMap = buildNodeMap(artifacts.deviceRegistry, artifacts.entityRegistry);
  const sceneSummaries = buildSceneSummaries(options.sceneIds);
  const cacheRampPlan = buildRampPlan(
    artifacts.valuesEntries,
    artifacts.metadataEntries,
    nodeMap
  );
  const suspiciousLogs = extractSuspiciousLogs(artifacts.zwaveLog);
  const accessToken = getAccessToken(options);
  const liveRampPlan = await filterPendingRampPlanWithLiveValues(
    options,
    accessToken,
    cacheRampPlan
  );

  const report = {
    generated_at: new Date().toISOString(),
    output_dir: outputDir,
    scene_summaries: sceneSummaries,
    cache_ramp_plan_count: cacheRampPlan.length,
    cache_ramp_plan: cacheRampPlan,
    live_ramp_plan_count: liveRampPlan.length,
    live_ramp_plan: liveRampPlan,
    suspicious_logs: suspiciousLogs,
  };

  writeJson(path.join(outputDir, "diagnostic-report.json"), report);
  writeJson(path.join(outputDir, "ramp-plan.json"), liveRampPlan);

  console.log(`Output directory: ${outputDir}`);
  console.log("");
  console.log("Scene summaries:");
  for (const summary of sceneSummaries) {
    console.log(
      `  ${summary.id}: ${summary.entityCount} entities -> ${summary.groupedCallCount} grouped calls`
    );
  }
  console.log("");
  console.log(`Pending ramp changes: ${liveRampPlan.length}`);
  for (const item of liveRampPlan.slice(0, 12)) {
    console.log(
      `  node ${item.nodeId} ${item.deviceName}: ${item.label} ${item.currentValue} -> ${item.targetValue}`
    );
  }
  if (liveRampPlan.length > 12) {
    console.log(`  ... ${liveRampPlan.length - 12} more`);
  }
  console.log("");
  console.log(`Ramp plan: ${path.join(outputDir, "ramp-plan.json")}`);
  console.log(`Diagnostic report: ${path.join(outputDir, "diagnostic-report.json")}`);

  if (suspiciousLogs.length > 0) {
    console.log("");
    console.log("Recent suspicious Z-Wave log lines:");
    for (const line of suspiciousLogs.slice(-10)) {
      console.log(`  ${line}`);
    }
  }
}

async function fetchConfigParameters(
  options: Options,
  accessToken: string,
  deviceId: string
): Promise<Record<string, JsonObject>> {
  return callHomeAssistantWs<Record<string, JsonObject>>(options, accessToken, {
    type: "zwave_js/get_config_parameters",
    device_id: deviceId,
  });
}

async function setConfigParameter(
  options: Options,
  accessToken: string,
  item: RampPlanItem
): Promise<void> {
  await callHomeAssistantWs(options, accessToken, {
    type: "zwave_js/set_config_parameter",
    device_id: item.deviceId,
    property: Number(item.parameter),
    endpoint: item.endpoint,
    value: item.targetValue,
  });
}

function readParameterValue(
  configParameters: Record<string, JsonObject>,
  item: RampPlanItem
): number | undefined {
  for (const parameter of Object.values(configParameters)) {
    if (
      Number(parameter.property) === Number(item.parameter) &&
      Number(parameter.endpoint ?? 0) === item.endpoint
    ) {
      return typeof parameter.value === "number" ? parameter.value : undefined;
    }
  }

  return undefined;
}

async function filterPendingRampPlanWithLiveValues(
  options: Options,
  accessToken: string,
  rampPlan: RampPlanItem[]
): Promise<RampPlanItem[]> {
  const configByDevice = new Map<string, Record<string, JsonObject>>();
  const remaining: RampPlanItem[] = [];

  for (const item of rampPlan) {
    if (!configByDevice.has(item.deviceId)) {
      configByDevice.set(
        item.deviceId,
        await fetchConfigParameters(options, accessToken, item.deviceId)
      );
    }

    const currentValue = readParameterValue(configByDevice.get(item.deviceId) ?? {}, item);
    if (currentValue !== item.targetValue) {
      remaining.push(item);
    }
  }

  return remaining;
}

async function applyInstantRamps(options: Options) {
  const outputDir = ensureOutputDir(options.outputDir);
  const artifactPaths = fetchLiveArtifacts(options, outputDir);
  const artifacts = loadArtifacts(artifactPaths);
  const nodeMap = buildNodeMap(artifacts.deviceRegistry, artifacts.entityRegistry);
  const rampPlan = buildRampPlan(
    artifacts.valuesEntries,
    artifacts.metadataEntries,
    nodeMap
  );
  const accessToken = getAccessToken(options);
  const applied: Array<{ item: RampPlanItem; result: string }> = [];

  for (const item of rampPlan) {
    await setConfigParameter(options, accessToken, item);
    applied.push({ item, result: "ok" });
  }

  writeJson(path.join(outputDir, "applied-ramp-plan.json"), applied);
  console.log(`Applied ${applied.length} ramp updates`);

  const configByDevice = new Map<string, Record<string, JsonObject>>();
  for (const item of rampPlan) {
    if (!configByDevice.has(item.deviceId)) {
      configByDevice.set(
        item.deviceId,
        await fetchConfigParameters(options, accessToken, item.deviceId)
      );
    }
  }

  const failed = applied.filter(({ item }) => {
    const currentValue = readParameterValue(configByDevice.get(item.deviceId) ?? {}, item);
    return currentValue !== item.targetValue;
  });

  writeJson(
    path.join(outputDir, "verify-pending.json"),
    failed.map(({ item }) => item)
  );

  if (failed.length > 0) {
    console.error(`Verification failed for ${failed.length} parameter updates`);
    process.exitCode = 1;
    return;
  }

  console.log(
    "Verification complete: all targeted ramp parameters are at their instant/fast values"
  );
}

async function verifyInstantRamps(options: Options) {
  const outputDir = ensureOutputDir(options.outputDir);
  const artifactPaths = fetchLiveArtifacts(options, outputDir);
  const artifacts = loadArtifacts(artifactPaths);
  const rampPlan = buildRampPlan(
    artifacts.valuesEntries,
    artifacts.metadataEntries,
    buildNodeMap(artifacts.deviceRegistry, artifacts.entityRegistry)
  );
  const accessToken = getAccessToken(options);
  const configByDevice = new Map<string, Record<string, JsonObject>>();
  const remaining: RampPlanItem[] = [];

  for (const item of rampPlan) {
    if (!configByDevice.has(item.deviceId)) {
      configByDevice.set(
        item.deviceId,
        await fetchConfigParameters(options, accessToken, item.deviceId)
      );
    }

    const currentValue = readParameterValue(configByDevice.get(item.deviceId) ?? {}, item);
    if (currentValue !== item.targetValue) {
      remaining.push(item);
    }
  }

  writeJson(path.join(outputDir, "verify-pending.json"), remaining);

  if (remaining.length > 0) {
    console.log(`Remaining non-instant ramp settings: ${remaining.length}`);
    for (const item of remaining.slice(0, 20)) {
      console.log(
        `  node ${item.nodeId} ${item.deviceName}: ${item.label} ${item.currentValue} -> ${item.targetValue}`
      );
    }
    process.exitCode = 1;
    return;
  }

  console.log("All targeted ramp parameters are already at their instant/fast values");
}

async function main() {
  const [command, ...args] = process.argv.slice(2);
  if (!command) {
    throw new Error("Usage: zwave-scenes <diagnose|apply-instant-ramps|verify-instant-ramps> [options]");
  }

  const options = parseArgs(args);

  switch (command) {
    case "diagnose":
      await diagnose(options);
      return;
    case "apply-instant-ramps":
      await applyInstantRamps(options);
      return;
    case "verify-instant-ramps":
      await verifyInstantRamps(options);
      return;
    default:
      throw new Error(`Unknown command: ${command}`);
  }
}

try {
  main();
} catch (error) {
  console.error(error instanceof Error ? error.message : error);
  process.exit(1);
}
