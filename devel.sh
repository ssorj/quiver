#!/usr/bin/env bash
echo $0
BASEDIR=$(readlink -f "$(dirname "$0}")")
echo $BASEDIR
export QUIVER_HOME=$BASEDIR/build/quiver
export PATH=$BASEDIR/build/bin:$BASEDIR/scripts:$PATH
export PYTHONPATH=$QUIVER_HOME/python:$BASEDIR/python${PYTHONPATH:+:${PYTHONPATH}}
export NODE_PATH=/usr/lib/node_modules${NODE_PATH:+:${NODE_PATH}}
