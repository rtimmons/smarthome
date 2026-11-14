#!/usr/bin/env bash
# Resolve private modules and enter their public Just recipes.
set -euo pipefail
workspace=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)
export SMARTHOME_WORKSPACE="$workspace"

require_module() {
    local name=$1 remote=$2 path="$workspace/$1"
    if [[ ! -d "$path" || ! -e "$path/.git" || ! -f "$path/Justfile" ]]; then
        printf 'Missing private checkout %s. From the workspace, run:\n  git clone %s %s\n' "$name" "$remote" "$name" >&2
        return 1
    fi
}

case "${1-}" in
    check)
        while read -r name remote; do
            require_module "$name" "$remote"
        done < "$workspace/workspace-modules"
        ;;
    run)
        shift
        requested=$1
        shift
        while read -r name remote; do
            if [[ "$name" == "$requested" ]]; then
                require_module "$name" "$remote"
                path="$workspace/$name"
                cd "$path"
                exec just --justfile "$path/Justfile" --working-directory "$path" "$@"
            fi
        done < "$workspace/workspace-modules"
        printf 'Unknown workspace module: %s\n' "$requested" >&2
        exit 2
        ;;
    *) exit 2 ;;
esac
