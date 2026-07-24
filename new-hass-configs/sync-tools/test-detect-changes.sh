#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DETECT_SCRIPT="${SCRIPT_DIR}/detect-changes.sh"
TEST_ROOT="$(mktemp -d /tmp/ha-drift-test.XXXXXX)"
trap 'rm -rf "$TEST_ROOT"' EXIT

make_fixture() {
    local fixture="$1"
    mkdir -p "$fixture/repo/manual" "$fixture/repo/generated" "$fixture/live/manual" "$fixture/live/generated"

    printf '%s\n' '- id: generated_scene' > "$fixture/repo/scenes.yaml"
    printf '%s\n' 'generated_script:' '  sequence: []' > "$fixture/repo/scripts.yaml"
    printf '%s\n' '[]' > "$fixture/repo/automations.yaml"
    printf '%s\n' '- id: manual_automation' > "$fixture/repo/manual/automations.yaml"
    printf '%s\n' '- id: generated_automation' > "$fixture/repo/generated/automations.yaml"

    cp -R "$fixture/repo/." "$fixture/live/"
}

run_detection() {
    local fixture="$1"
    SYNC_CONFIG_DIR="$fixture/repo" \
    SYNC_LIVE_CONFIG_DIR="$fixture/live" \
    SYNC_TEMP_DIR="$fixture/work" \
        "$DETECT_SCRIPT"
}

repository_changes_are_deployable() {
    local fixture="$TEST_ROOT/repository-change"
    make_fixture "$fixture"
    printf '%s\n' 'generated_script:' '  sequence:' '    - action: light.turn_on' > "$fixture/repo/scripts.yaml"
    printf '%s\n' '- id: generated_automation' '  actions: []' > "$fixture/repo/generated/automations.yaml"
    run_detection "$fixture" >/dev/null 2>&1
}

ui_automation_changes_block() {
    local fixture="$TEST_ROOT/ui-automation-change"
    make_fixture "$fixture"
    printf '%s\n' "- id: '1750000000000'" '  alias: UI automation' > "$fixture/live/automations.yaml"
    ! run_detection "$fixture" >/dev/null 2>&1
}

new_ui_scene_ids_block() {
    local fixture="$TEST_ROOT/ui-scene-change"
    make_fixture "$fixture"
    printf '%s\n' '- id: generated_scene' "- id: '1750000000001'" > "$fixture/live/scenes.yaml"
    ! run_detection "$fixture" >/dev/null 2>&1
}

repository_changes_are_deployable
ui_automation_changes_block
new_ui_scene_ids_block

echo "detect-changes regression tests passed"
