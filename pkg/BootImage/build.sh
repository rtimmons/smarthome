#!/usr/bin/env bash
set -eou pipefail

pkg() {
    pushd pi-gen
        echo "IMG_NAME=rypi" > config
        touch stage{3,4,5}/SKIP
        rm stage2/EXPORT*
        ./build-docker.sh
    popd
}

fn="$1"
shift
"$fn" "$@"
