#!/usr/bin/env bash

if [[ "${1}" == "list-dependencies" ]]; then
    echo "Ansible"
    exit 0
fi

set -eou pipefail

pushd "$(dirname "$0")" >/dev/null || exit
    FlaskServerDir="$(pwd -P)"
popd > /dev/null || exit 1

cd "$FlaskServerDir" || exit 1

poetry build

mkdir -p build/PythonWheels
cp dist/flaskserver-0.0.0-py3-none-any.whl ./build/PythonWheels/
