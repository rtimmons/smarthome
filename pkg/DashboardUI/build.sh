#!/usr/bin/env bash


test() {
    ./node_modules/mocha/bin/mocha
}


fn=$1
shift

eval "$fn" "$@"
