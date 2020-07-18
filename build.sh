#!/usr/bin/env bash

set -eo pipefail

pushd "$(dirname "$0")" >/dev/null || exit 1
    MYDIR="$(pwd -P)"
popd >/dev/null || exit 1

cd "$MYDIR" || exit 1

mkdir -p build/bin build/tmp
export PATH="$MYDIR/build/bin:$PATH"

VENV_PATH="$MYDIR/build/tmp"
if [ ! -e "$VENV_PATH/venv/setup-done" ]; then
    rm -rf "$VENV_PATH/venv"
    pushd "$VENV_PATH" >/dev/null || exit 1
        python3 -m venv venv
        touch "$VENV_PATH/venv/setup-done"
    popd >/dev/null || exit 1
fi
source "$VENV_PATH/venv/bin/activate"
unset VENV_PATH


# echo "[DEBUG] Building ocho with path=$PATH"

./ocho/build.sh

ocho "$@"
