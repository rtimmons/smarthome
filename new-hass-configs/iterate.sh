#!/usr/bin/env bash
set -euo pipefail

# Run from the repo root or anywhere; snapshots land under new-hass-configs/inventory_snapshots/
cd "$(dirname "${BASH_SOURCE[0]}")"

timestamp=$(date +"%Y%m%d-%H%M%S")
snap_dir="inventory_snapshots/${timestamp}"
mkdir -p "${snap_dir}"

echo "Taking pre-scene inventory..."
just inventory
cp device_inventory.json "${snap_dir}/device_before.json"
cp entity_inventory.json "${snap_dir}/entity_before.json"

echo "Applying guest bathroom high scene via hass-cli..."
hass-cli service call scene.turn_on --arguments entity_id=scene.guest_bathroom_high

echo "Taking post-scene inventory..."
just inventory
cp device_inventory.json "${snap_dir}/device_after.json"
cp entity_inventory.json "${snap_dir}/entity_after.json"

echo "Done. Snapshot saved to ${snap_dir}"
