#!/usr/bin/env bash
set -eou pipefail

mkdir -p /tmp/python39
cd /tmp/python39

if [ ! -d "Python-3.9.0" ]; then
    if [ ! -e "Python-3.9.0.tgz" ]; then
        wget "https://www.python.org/ftp/python/3.9.0/Python-3.9.0.tgz"
    fi
    tar xzf Python-3.9.0.tgz
fi

cd Python-3.9.0
./configure --enable-loadable-sqlite-extensions
make -j4
make install

hash -r
pip3.9 install --upgrade pip setuptools wheel
