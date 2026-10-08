interface HealthNode {
  nodeId: number;
  name?: string;
  entityIds: string[];
}

interface HealthState {
  entity_id: string;
  state: string;
  last_changed?: string;
}

/** Evidence from the captured log window, not a claim of whole-network health. */
export function buildNetworkHealth(
  nodes: Iterable<HealthNode>,
  states: HealthState[],
  logSummary: { nodeCounts: Array<{ nodeId: number; count: number }> },
  logText: string
) {
  const stateMap = new Map(states.map((state) => [state.entity_id, state]));
  const errors = new Map(logSummary.nodeCounts.map((item) => [item.nodeId, item.count]));
  const timestamps = [...logText.matchAll(/^\s*(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?)/gm)]
    .map((match) => match[1]).sort();
  const reports = [...nodes].map((node) => {
    const statusId = node.entityIds.find((id) => id.endsWith("_node_status"));
    const status = statusId ? stateMap.get(statusId) : undefined;
    const errorCount = errors.get(node.nodeId) ?? 0;
    const unhealthy = ["dead", "unavailable", "unknown"].includes(status?.state ?? "unknown");
    return {
      nodeId: node.nodeId,
      deviceName: node.name,
      nodeStatusEntityId: statusId,
      state: status?.state ?? "missing",
      statusLastChanged: status?.last_changed,
      capturedErrorCount: errorCount,
      assessment: !status ? "status_unavailable" : unhealthy ? "unhealthy" : errorCount ? "errors_despite_available_status" : "no_fault_observed",
      // Cached load state must not overrule the node's own health sensor.
      apparentlyAvailableLoadsOnUnhealthyNode: unhealthy ? node.entityIds.filter((id) =>
        /^(light|switch)\./.test(id) && ["on", "off"].includes(stateMap.get(id)?.state ?? "")
      ) : [],
    };
  }).sort((a, b) => a.nodeId - b.nodeId);
  return {
    scope: "Current node status plus errors in the captured log window; no active reachability or physical-output test.",
    logWindow: {
      firstTimestamp: timestamps[0] ?? null,
      lastTimestamp: timestamps[timestamps.length - 1] ?? null,
      timestampTimezone: "As emitted by Z-Wave JS; no timezone assumed",
      lineCount: logText ? logText.split("\n").filter(Boolean).length : 0,
    },
    nodes: reports,
    errorsWithoutRegistryNode: logSummary.nodeCounts.filter((item) => !reports.some((node) => node.nodeId === item.nodeId)),
  };
}
