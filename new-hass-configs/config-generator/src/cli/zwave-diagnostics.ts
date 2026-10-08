const CACHE_DIRECTORIES = [
  "/app_configs/core_zwave_js/cache",
  "/addon_configs/core_zwave_js/cache",
];

function shellQuote(value: string): string {
  return `'${value.replace(/'/g, `'"'"'`)}'`;
}

// Resolve a matching pair from one home ID; never mix caches across layouts.
export function cacheDiscoveryCommand(directories = CACHE_DIRECTORIES): string {
  return `
for cache_dir in ${directories.map(shellQuote).join(" ")}; do
  for values in "$cache_dir"/*.values.jsonl; do
    [ -f "$values" ] || continue
    metadata="\${values%.values.jsonl}.metadata.jsonl"
    [ -f "$metadata" ] || continue
    printf '%s\\n%s\\n' "$values" "$metadata"
    exit 0
  done
done
printf '%s\\n' ${shellQuote(`Z-Wave cache missing: no matching values/metadata JSONL pair in ${directories.join(" or ")}. Check the Z-Wave JS app and its cache mount.`)} >&2
exit 1
`.trim();
}

export function parseCachePaths(output: string): { values: string; metadata: string } {
  const paths = output.trim().split(/\r?\n/);
  if (
    paths.length !== 2 ||
    !paths[0].startsWith("/") ||
    !paths[0].endsWith(".values.jsonl") ||
    paths[1] !== paths[0].replace(/\.values\.jsonl$/, ".metadata.jsonl")
  ) {
    throw new Error("Z-Wave cache discovery did not return a matching values/metadata JSONL pair.");
  }
  return { values: paths[0], metadata: paths[1] };
}

export function diagnosticLogCommands(logLines: number): { zwave: string; core: string } {
  if (!Number.isInteger(logLines) || logLines < 1 || logLines > 4294967295) {
    throw new Error("--log-lines must be an integer between 1 and 4294967295.");
  }
  return {
    zwave: `ha apps logs core_zwave_js --lines ${logLines}`,
    core: `ha core logs --lines ${logLines}`,
  };
}
