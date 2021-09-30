#!/usr/bin/env bash
set -eou pipefail

mkdir -p /tmp/python38
cd /tmp/python38

if [ ! -d "Python-3.8.11" ]; then
    if [ ! -e "Python-3.8.11.tgz" ]; then
        wget "https://www.python.org/ftp/python/3.8.11/Python-3.8.11.tgz"
    fi
    tar xzf Python-3.8.11.tgz
fi

cd Python-3.8.11
./configure --enable-loadable-sqlite-extensions
make -j4
make install

hash -r
pip3.8 install --upgrade pip setuptools wheel
