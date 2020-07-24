#!/usr/bin/env bash
set -Eeuxo pipefail

BASEDIR=$(readlink -f "$(dirname "$0")")
export QUIVER_HOME=$BASEDIR/build/quiver
export PATH=$PWD/build/bin:$BASEDIR/scripts:$PATH
export PYTHONPATH=$QUIVER_HOME/python:$BASEDIR/python${$PYTHONPATH:+:${PYTHONPATH}}
export NODE_PATH=/usr/lib/node_modules${$NODE_PATH:+:${NODE_PATH}}
