#!/usr/bin/env bash
set -euo pipefail
# Keep credentials out of command arguments and stdout, including bash -x use.
set +x
umask 077

if [[ $# -gt 1 || ( $# -eq 1 && "$1" != --check ) ]]; then
  echo 'Usage: run.sh [--check]' >&2
  exit 2
fi

UNIFI_API_KEY="${UBIQUITI_API_KEY:-}"
if [[ -z "$UNIFI_API_KEY" || "$UNIFI_API_KEY" == *[[:space:]]* ]]; then
  echo 'UniFi MCP: set UBIQUITI_API_KEY to a nonempty single-line token in the MCP settings.' >&2
  exit 1
fi
export UNIFI_API_KEY
unset UBIQUITI_API_KEY
export UNIFI_API_TYPE=local
export UNIFI_LOCAL_HOST=192.168.1.1
export UNIFI_LOCAL_PORT=443
export UNIFI_LOCAL_VERIFY_SSL=false
export UNIFI_DEFAULT_SITE=default
export UNIFI_SITE_MANAGER_ENABLED=false
export UNIFI_PROFILE=network
export UNIFI_READ_ONLY=false
export UNIFI_DRY_RUN=false
export UNIFI_STDIO_ROLE=admin
export MCP_SERVER_TRANSPORT=stdio
export AGNOST_ENABLED=false
export SUPERMEMORY_ENABLED=false
export UNIFI_METRICS_ENABLED=false
export LOG_API_REQUESTS=false
export LOG_LEVEL=WARNING
unset DEBUG DATABASE_URL REDIS_URL REDIS_HOST UNIFI_LOCAL_CA_FILE
unset UNIFI_AUDIT_SIEM_TARGETS UNIFI_AUDIT_SIEM_WEBHOOK_SECRET UNIFI_AUDIT_SIEM_OTLP_HEADERS

# Do not load an unrelated project's .env when a desktop client chooses cwd.
launcher_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$launcher_dir/../.." && pwd)"
export UV_CACHE_DIR="$repo_root/build/unifi-mcp/uv-cache"
export UV_TOOL_DIR="$repo_root/build/unifi-mcp/tools"
export UV_TOOL_BIN_DIR="$repo_root/build/unifi-mcp/bin"
export UV_PYTHON_DOWNLOADS=never
export UNIFI_AUDIT_LOG_ENABLED=true
export UNIFI_AUDIT_FAIL_CLOSED=true
export UNIFI_AUDIT_LOG_PATH="$repo_root/build/unifi-mcp/audit.jsonl"
cd "$launcher_dir"
# v0.6.1 exists on GitHub, but is not published on PyPI. Use its exact commit.
unifi_source='git+https://github.com/enuno/unifi-mcp-server.git@12b4c6e964f920806e2604ab8554e98a4b92536f'
if [[ "${1:-}" == --check ]]; then
  exec /opt/homebrew/bin/uvx --python "$(cat "$repo_root/.python-version")" --from "$unifi_source" python "$launcher_dir/check.py"
fi
exec /opt/homebrew/bin/uvx --python "$(cat "$repo_root/.python-version")" --from "$unifi_source" python "$launcher_dir/server.py"
