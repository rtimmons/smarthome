#!/usr/bin/env bash
set -eou pipefail

mkdir -p /tmp/python311
cd /tmp/python311

if [ ! -d "Python-3.11.4" ]; then
    if [ ! -e "Python-3.11.4.tgz" ]; then
        wget "https://www.python.org/ftp/python/3.11.4/Python-3.11.4.tgz"
    fi
    tar xzf Python-3.11.4.tgz
fi

cd Python-3.11.4
./configure --enable-loadable-sqlite-extensions
make -j4
make install

hash -r
pip3.11 install --upgrade pip setuptools wheel
