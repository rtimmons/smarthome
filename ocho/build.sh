#!/usr/bin/env bash

set -eou pipefail

if ! command -v poetry &> /dev/null; then
    python3 -m pip install poetry -q -q
fi

cd "$(dirname "$0")" || exit 1

#if command -v ocho &> /dev/null; then
#    exit 0
#fi

poetry -q build
python3 -m pip install ./dist/ocho-*.whl -q -q
