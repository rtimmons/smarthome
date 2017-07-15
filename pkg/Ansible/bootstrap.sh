#!/usr/bin/env bash

if [ ! -e "/Applications/Docker.app" ]; then
    brew cask install docker
fi
