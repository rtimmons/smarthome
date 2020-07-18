#!/usr/bin/env bash

set -eou pipefail

if ! command -v poetry &> /dev/null; then
    python3 -m pip install poetry -q -q
fi

cd "$(dirname "$0")" || exit 7

#if command -v ocho &> /dev/null; then
#    exit 0
#fi

rm -f ./dist/*

# the -q option makes it nop?
poetry build >/dev/null 2>/dev/null

python3 -m pip install --force-reinstall ./dist/ocho-0.0.0-py3-none-any.whl -q -q || exit 39
