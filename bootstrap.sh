#!/usr/bin/env bash

uname -a | grep Darwin >/dev/null
if [ ! $? ]; then
    echo "Can only run on a mac for now"
    exit 1
fi

for P in pkg/*; do
    if [ -e "$P/bootstrap.sh" ]; then
        echo "👢 Package $(basename $P)"
        pushd "$P" >/dev/null
            "./bootstrap.sh"
        popd >/dev/null
    fi
done