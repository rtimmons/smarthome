import { buildNetworkHealth } from "./zwave-health";

describe("combined Z-Wave health", () => {
  const nodes = [
    { nodeId: 4, entityIds: ["sensor.plug_node_status", "light.plug"] },
    { nodeId: 21, entityIds: ["sensor.closet_node_status"] },
    { nodeId: 1, entityIds: [] },
  ];
  it("flags alive nodes with errors and dead nodes with misleading cached load states", () => {
    const report = buildNetworkHealth(nodes, [
      { entity_id: "sensor.plug_node_status", state: "dead", last_changed: "2026-10-05T23:41:37Z" },
      { entity_id: "light.plug", state: "on" },
      { entity_id: "sensor.closet_node_status", state: "alive" },
    ], { nodeCounts: [{ nodeId: 21, count: 2 }] }, "2026-10-06 06:56:07.569 Node 021 timed out\n2026-10-06 06:56:13.629 Node 021 timed out");
    expect(report.nodes.find((n) => n.nodeId === 4)).toMatchObject({ assessment: "unhealthy", apparentlyAvailableLoadsOnUnhealthyNode: ["light.plug"] });
    expect(report.nodes.find((n) => n.nodeId === 21)).toMatchObject({ assessment: "errors_despite_available_status", capturedErrorCount: 2 });
    expect(report.nodes.find((n) => n.nodeId === 1)?.assessment).toBe("status_unavailable");
    expect(report.logWindow.firstTimestamp).toBe("2026-10-06 06:56:07.569");
  });
  it("preserves unknown-node errors and does not invent log coverage", () => {
    const report = buildNetworkHealth([], [], { nodeCounts: [{ nodeId: 99, count: 3 }] }, "");
    expect(report.errorsWithoutRegistryNode).toEqual([{ nodeId: 99, count: 3 }]);
    expect(report.logWindow).toMatchObject({ firstTimestamp: null, lastTimestamp: null, lineCount: 0 });
  });
});
