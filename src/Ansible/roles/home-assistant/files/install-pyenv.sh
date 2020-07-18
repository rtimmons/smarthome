#!/usr/bin/env bash
set -eou pipefail

mkdir -p /tmp/python38
cd /tmp/python38

if [ ! -d "Python-3.8.1" ]; then
    if [ ! -e "Python-3.8.1.tgz" ]; then
        wget "https://www.python.org/ftp/python/3.8.1/Python-3.8.1.tgz"
    fi
    tar xzf Python-3.8.1.tgz
fi

cd Python-3.8.1
./configure --enable-loadable-sqlite-extensions
make -j4
make install
