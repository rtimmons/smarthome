#!/usr/bin/env bash

set -eo pipefail

pushd "$(dirname "$0")" >/dev/null || exit 1
    MYDIR="$(pwd -P)"
popd >/dev/null || exit 1

cd "$MYDIR" || exit 1

mkdir -p build/bin build/tmp

if [ ! -e "$MYDIR/build/tmp/venv/setup-done" ]; then
    rm -rf "$MYDIR/build/tmp/venv"
    pushd "$MYDIR/build/tmp" >/dev/null || exit 1
        python3 -m venv venv
        touch "$MYDIR/build/tmp/venv/setup-done"
    popd >/dev/null || exit 1
fi

source "$MYDIR/build/venv/bin/activate"

export PATH="$MYDIR/build/bin:$PATH"

./ocho/build.sh

ocho "$@"
