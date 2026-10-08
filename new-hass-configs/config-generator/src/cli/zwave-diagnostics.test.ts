import { execFileSync, spawnSync } from "child_process";
import * as fs from "fs";
import * as os from "os";
import * as path from "path";
import { cacheDiscoveryCommand, diagnosticLogCommands, parseCachePaths } from "./zwave-diagnostics";

describe("Z-Wave diagnostic collection", () => {
  let root: string;
  let directories: string[];

  beforeEach(() => {
    root = fs.mkdtempSync(path.join(os.tmpdir(), "zwave-cache-test-"));
    directories = ["app_configs", "addon_configs"].map((name) => path.join(root, name));
    directories.forEach((directory) => fs.mkdirSync(directory));
  });
  afterEach(() => fs.rmSync(root, { recursive: true, force: true }));

  function pair(directory: string, id = "network") {
    fs.writeFileSync(path.join(directory, `${id}.values.jsonl`), "");
    fs.writeFileSync(path.join(directory, `${id}.metadata.jsonl`), "");
  }
  function discover() {
    return parseCachePaths(execFileSync("sh", ["-c", cacheDiscoveryCommand(directories)], { encoding: "utf8" }));
  }

  it("prefers app_configs when both layouts exist", () => {
    directories.forEach((directory) => pair(directory));
    expect(discover().values).toBe(path.join(directories[0], "network.values.jsonl"));
  });
  it("falls back to a complete legacy pair when the current cache is incomplete", () => {
    fs.writeFileSync(path.join(directories[0], "old.values.jsonl"), "");
    pair(directories[1]);
    expect(discover().metadata).toBe(path.join(directories[1], "network.metadata.jsonl"));
  });
  it("fails clearly when caches are absent or different home IDs cannot be paired", () => {
    fs.writeFileSync(path.join(directories[0], "first.values.jsonl"), "");
    fs.writeFileSync(path.join(directories[0], "second.metadata.jsonl"), "");
    const result = spawnSync("sh", ["-c", cacheDiscoveryCommand(directories)], { encoding: "utf8" });
    expect(result.status).toBe(1);
    expect(result.stdout).toBe("");
    expect(result.stderr).toContain("Z-Wave cache missing: no matching values/metadata JSONL pair");
    expect(result.stderr).toContain(directories[0]);
    expect(result.stderr).toContain(directories[1]);
  });
  it("rejects empty or mismatched discovery output before attempting copies", () => {
    expect(() => parseCachePaths("")).toThrow("matching values/metadata");
    expect(() => parseCachePaths("/a.values.jsonl\n/b.metadata.jsonl")).toThrow("matching values/metadata");
  });
  it("requests the log window from HA directly without a pipeline masking failures", () => {
    expect(diagnosticLogCommands(2000)).toEqual({
      zwave: "ha apps logs core_zwave_js --lines 2000",
      core: "ha core logs --lines 2000",
    });
    for (const value of [NaN, 0, -1, 1.5, Infinity, 4294967296]) {
      expect(() => diagnosticLogCommands(value)).toThrow("--log-lines");
    }
  });
});
