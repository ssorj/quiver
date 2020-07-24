#!/usr/bin/env bash
BASEDIR=$(readlink -f "$(dirname "${BASH_SOURCE[0]:-$0}")")
export QUIVER_HOME=$BASEDIR/build/quiver
export PATH=$BASEDIR/build/bin:$BASEDIR/scripts:$PATH
export PYTHONPATH=$QUIVER_HOME/python:$BASEDIR/python${PYTHONPATH:+:${PYTHONPATH}}
export NODE_PATH=/usr/lib/node_modules${NODE_PATH:+:${NODE_PATH}}
