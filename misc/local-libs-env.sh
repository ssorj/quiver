export LIBRARY_PATH=$HOME/.local/lib64:/usr/local/lib64
export C_INCLUDE_PATH=$HOME/.local/include:/usr/local/include
export CPLUS_INCLUDE_PATH=$C_INCLUDE_PATH
export LD_LIBRARY_PATH=$LIBRARY_PATH
export PYTHONPATH=$HOME/.local/lib/python2.7/site-packages:$HOME/.local/lib64/python2.7/site-packages:$PYTHONPATH

if [[ -f $HOME/.local/lib64/libqpid-proton-cpp.so || -f /usr/local/lib64/libqpid-proton-cpp.so ]]; then
    export QPID_PROTON_CPP_ENABLED=1
fi
