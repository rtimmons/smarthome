#!/usr/bin/env bash
set -euo pipefail

# Pre-setup validation for printer service
# Note: Basic cairo installation is handled by talos/setup_dev_env.sh
# This hook only validates cairo is functional for Python/cairocffi

echo "[printer] Validating cairo configuration for cairocffi..." >&2

# Verify pkg-config can find cairo (needed by cairocffi)
if ! command -v pkg-config >/dev/null 2>&1; then
    echo "[printer] WARNING: pkg-config not found - skipping cairo validation" >&2
    exit 0
fi

brew_prefix="$(brew --prefix 2>/dev/null || echo "/usr/local")"
export PKG_CONFIG_PATH="${brew_prefix}/lib/pkgconfig:${brew_prefix}/share/pkgconfig:${PKG_CONFIG_PATH:-}"

if ! pkg-config --exists cairo 2>/dev/null; then
    echo "[printer] WARNING: pkg-config cannot find cairo" >&2
    echo "[printer] If setup already ran, this might indicate a PATH issue" >&2
    exit 0
fi

cairo_version=$(pkg-config --modversion cairo 2>/dev/null || echo "unknown")
echo "[printer] ✓ cairo library configured (version: $cairo_version)" >&2
exit 0
