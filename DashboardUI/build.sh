#!/usr/bin/env bash

brew bundle exec -- npm install

test() {
    brew bundle exec -- npm test
}


fn=$1
shift

eval "$fn" "$@"
