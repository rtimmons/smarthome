#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $(basename "$0") <recipe> [addon...]" >&2
}

if [ $# -lt 1 ]; then
  usage
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$REPO_ROOT"

if [ -d "$REPO_ROOT/.venv/bin" ]; then
  export PATH="$REPO_ROOT/.venv/bin:$PATH"
fi
export REPO_ROOT

recipe="$1"
shift

# Discover add-ons (directories containing addon.yaml) unless a list was provided.
discover_addons() {
  shopt -s nullglob
  local manifests=(*/*/addon.yaml */addon.yaml)
  shopt -u nullglob

  local dirs=()
  for manifest in "${manifests[@]}"; do
    [ -f "$manifest" ] || continue
    dirs+=("$(dirname "$manifest")")
  done

  if [ ${#dirs[@]} -eq 0 ]; then
    echo "No add-on manifests found (expected */addon.yaml)." >&2
    return 1
  fi

  printf "%s\n" "${dirs[@]}" | sort
}

addons=()
if [ $# -gt 0 ]; then
  for name in "$@"; do
    if [ -d "$name" ] && [ -f "$name/addon.yaml" ]; then
      addons+=("$name")
    else
      echo "Unknown add-on '$name' (no addon.yaml in $name)." >&2
      exit 1
    fi
  done
else
if ! addons_output=$(discover_addons); then
  exit 1
fi
while IFS= read -r line; do
  addons+=("$line")
done <<EOF
$addons_output
EOF
fi

has_recipe() {
  local dir="$1" target="$2"
  just --justfile "$dir/Justfile" --working-directory "$dir" --color never --list 2>/dev/null \
    | tail -n +2 \
    | awk '{print $1}' \
    | grep -Fxq "$target"
}

run_recipe() {
  local dir="$1"

  if [ ! -f "$dir/Justfile" ]; then
    echo "==> ${dir}: skipping, no Justfile"
    return
  fi

  if [ "$recipe" = "deploy" ]; then
    # Run common pre-deploy steps when they exist to ensure artifacts are fresh.
    for pre in generate build test ha-addon; do
      if has_recipe "$dir" "$pre"; then
        echo "==> ${dir}: just $pre (pre-deploy)"
        just --justfile "$dir/Justfile" --working-directory "$dir" "$pre"
      fi
    done
  fi

  if has_recipe "$dir" "$recipe"; then
    echo "==> ${dir}: just $recipe"
    just --justfile "$dir/Justfile" --working-directory "$dir" "$recipe"
  else
    echo "==> ${dir}: skipping, no '$recipe' recipe"
  fi
}

for addon in "${addons[@]}"; do
  run_recipe "$addon"
done
