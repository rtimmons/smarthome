#!/usr/bin/env bash

if [ ! -e "/Applications/Docker.app" ]; then
    brew cask install docker
fi

docker build . >/dev/null

if [ ! -e "root" ]; then
    mkdir root
fi

pushd root >/dev/null
    if [ ! -d dasher ]; then
        git clone https://github.com/maddox/dasher.git
        pushd dasher >/dev/null
            npm install
        popd
    fi

    if [ ! -d "node-sonos-http-api" ]; then
        git clone https://github.com/jishi/node-sonos-http-api
        pushd node-sonos-http-api >/dev/null
            npm install --production
        popd >/dev/null
    fi
popd >/dev/null
