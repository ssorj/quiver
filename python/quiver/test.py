#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#

from __future__ import print_function

import sys as _sys

from plano import *
from quiver.common import *

def init_test_module():
    set_message_threshold("error")

def test_common_options():
    commands = [
        "quiver",
        "quiver-arrow",
        "quiver-bench",
        "quiver-launch",
        "quiver-server",
    ]

    for command in commands:
        call("{} --help", command)
        call("{} --version", command)

def test_quiver_arrow():
    call("quiver-arrow send q0 --init-only")
    call("quiver-arrow --init-only receive q0")

    for impl in ARROW_IMPLS:
        if impl_exists(impl):
            call("quiver-arrow --impl {} --impl-info", impl)

def test_quiver_server():
    for impl in SERVER_IMPLS:
        if impl == "activemq" and which("activemq") is None:
            continue

        if impl == "activemq-artemis" and which("artemis") is None:
            continue

        if impl == "qpid-cpp" and which("qpidd") is None:
            continue

        if impl == "qpid-dispatch" and which("qdrouterd") is None:
            continue

        call("quiver-server --impl {} --impl-info", impl)

        if impl == "activemq-artemis":
            # XXX Permissions problem
            continue

        with _TestServer(impl=impl) as server:
            call("quiver {} -m 1", server.url)

def test_quiver_launch_client_server():
    with _TestServer() as server:
        call("quiver-launch {} --count 2 --options \"-m 1\" --verbose", server.url)

def test_quiver_launch_peer_to_peer():
    call("quiver-launch --sender-options=\"-m 1\" --receiver-options=\"-m 1 --server --passive\" --verbose {}", _test_url())

def test_quiver_pair_client_server():
    # XXX full matrix

    with _TestServer() as server:
        call("quiver {} --arrow qpid-proton-python -m 1 --verbose", server.url)

        if impl_exists("qpid-jms"):
            call("quiver {} --arrow qpid-jms -m 1 --verbose", server.url)

        if impl_exists("vertx-proton"):
            call("quiver {} --arrow vertx-proton -m 1 --verbose", server.url)

def test_quiver_pair_peer_to_peer():
    # XXX full matrix

    call("quiver {} --arrow qpid-proton-python -m 1 --peer-to-peer --verbose", _test_url())

    if impl_exists("rhea"):
        call("quiver {} --arrow rhea -m 1 --peer-to-peer --verbose", _test_url())

def test_quiver_bench():
    command = [
        "quiver-bench",
        "-m", "1",
        "--include-servers", "builtin",
        "--exclude-servers", "none",
        "--verbose",
        "--output", make_temp_dir(),
    ]

    call(command)

class _TestServer(running_process):
    def __init__(self, impl="builtin", **kwargs):
        port = random_port()

        self.url = "//127.0.0.1:{}/q0".format(port)
        self.ready_file = make_temp_file()

        command = [
            "quiver-server", self.url,
            "--verbose",
            "--ready-file", self.ready_file,
            "--impl", impl,
        ]

        super(_TestServer, self).__init__(command, **kwargs)

    def __enter__(self):
        super(_TestServer, self).__enter__()

        self.proc.url = self.url

        for i in range(30):
            if read(self.ready_file) == "ready\n":
                break

            sleep(0.2)

        return self.proc

def _test_url():
    return "//127.0.0.1:{}/q0".format(random_port())
