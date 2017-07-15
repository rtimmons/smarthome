#!/usr/bin/env bash
set -eou pipefail

pkg() {
    docker rm -v pigen_work || echo ""
    pushd vendor/pi-gen >/dev/null
        echo "IMG_NAME=rypi" > config
        touch stage{3,4,5}/SKIP
        rm stage2/EXPORT* || echo ""
        ./build-docker.sh
    popd >/dev/null
}

install() {
    # TODO: wip
    diskutil list
    diskutil unmountDisk /dev/disk2
    brew install p7zip
    brew install pv

    sudo \
        dd if="raspbian-lite-pibakery-new.img" \
        | pv | \
        dd of=/dev/disk2 \
           bs=1m
}

fn="$1"
shift
"$fn" "$@"
