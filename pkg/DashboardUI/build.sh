#!/usr/bin/env bash


test() {
    npm test
}


fn=$1
shift

eval "$fn" "$@"
