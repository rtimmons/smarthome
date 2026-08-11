#!/usr/bin/env node

import * as fs from "fs";
import * as path from "path";

import {
  callHomeAssistantWs,
  callService,
  DEFAULT_HASS_HOST,
  DEFAULT_HASS_SERVER,
  fetchState,
  getAccessToken,
  HomeAssistantConnectionOptions,
  JsonObject,
} from "./home-assistant-client";

type Command = "devices" | "entities" | "inventory" | "state" | "call";

export interface CliOptions extends HomeAssistantConnectionOptions {
  command: Command;
  deviceOutput: string;
  entityOutput: string;
  entityId?: string;
  service?: string;
  data: Record<string, any>;
}

function requireValue(argv: string[], index: number, flag: string): string {
  const value = argv[index + 1];
  if (!value || value.startsWith("--")) {
    throw new Error(`${flag} requires a value`);
  }
  return value;
}

export function parseArgs(
  argv: string[],
  env: NodeJS.ProcessEnv = process.env
): CliOptions {
  const [rawCommand, ...args] = argv;
  if (!["devices", "entities", "inventory", "state", "call"].includes(rawCommand)) {
    throw new Error(
      "Usage: home-assistant <devices|entities|inventory|state|call> [options]"
    );
  }

  const options: CliOptions = {
    command: rawCommand as Command,
    host: env.HASS_HOST ?? DEFAULT_HASS_HOST,
    server: env.HASS_SERVER ?? DEFAULT_HASS_SERVER,
    deviceOutput: "device_inventory.json",
    entityOutput: "entity_inventory.json",
    data: {},
  };
  const positional: string[] = [];

  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    switch (arg) {
      case "--host":
        options.host = requireValue(args, index, arg);
        index += 1;
        break;
      case "--server":
        options.server = requireValue(args, index, arg);
        index += 1;
        break;
      case "--device-output":
        options.deviceOutput = requireValue(args, index, arg);
        index += 1;
        break;
      case "--entity-output":
        options.entityOutput = requireValue(args, index, arg);
        index += 1;
        break;
      case "--entity-id":
        options.data.entity_id = requireValue(args, index, arg);
        index += 1;
        break;
      case "--data": {
        const value = requireValue(args, index, arg);
        const parsed = JSON.parse(value);
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
          throw new Error("--data must be a JSON object");
        }
        options.data = { ...options.data, ...parsed };
        index += 1;
        break;
      }
      default:
        if (arg.startsWith("--")) {
          throw new Error(`Unknown option: ${arg}`);
        }
        positional.push(arg);
    }
  }

  if (options.command === "state") {
    if (positional.length !== 1) {
      throw new Error("Usage: home-assistant state <entity_id> [connection options]");
    }
    options.entityId = positional[0];
  } else if (options.command === "call") {
    if (positional.length !== 1 || !/^[^.]+\.[^.]+$/.test(positional[0])) {
      throw new Error(
        "Usage: home-assistant call <domain.service> [--entity-id <entity_id>] [--data <json>]"
      );
    }
    options.service = positional[0];
  } else if (positional.length > 0) {
    throw new Error(`Unexpected argument: ${positional[0]}`);
  }

  return options;
}

function printJson(value: unknown) {
  process.stdout.write(`${JSON.stringify(value, null, 2)}\n`);
}

function writeJson(filePath: string, value: unknown) {
  const resolved = path.resolve(filePath);
  fs.mkdirSync(path.dirname(resolved), { recursive: true });
  fs.writeFileSync(resolved, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

export async function main(argv: string[] = process.argv.slice(2)) {
  const options = parseArgs(argv);
  const accessToken = getAccessToken(options);

  switch (options.command) {
    case "devices":
      printJson(
        await callHomeAssistantWs<JsonObject[]>(options, accessToken, {
          type: "config/device_registry/list",
        })
      );
      return;
    case "entities":
      printJson(
        await callHomeAssistantWs<JsonObject[]>(options, accessToken, {
          type: "config/entity_registry/list",
        })
      );
      return;
    case "inventory": {
      const devices = await callHomeAssistantWs<JsonObject[]>(options, accessToken, {
        type: "config/device_registry/list",
      });
      const entities = await callHomeAssistantWs<JsonObject[]>(options, accessToken, {
        type: "config/entity_registry/list",
      });
      writeJson(options.deviceOutput, devices);
      writeJson(options.entityOutput, entities);
      console.log(`Wrote device inventory to ${options.deviceOutput}`);
      console.log(`Wrote entity inventory to ${options.entityOutput}`);
      return;
    }
    case "state": {
      const state = fetchState(options, accessToken, options.entityId!);
      if (!state) {
        throw new Error(`Entity not found: ${options.entityId}`);
      }
      printJson(state);
      return;
    }
    case "call": {
      const [domain, service] = options.service!.split(".", 2);
      printJson(callService(options, accessToken, domain, service, options.data));
      return;
    }
  }
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : error);
    process.exit(1);
  });
}
