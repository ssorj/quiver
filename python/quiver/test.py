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

import argparse
import sys

from plano import *
from quiver.common import ARROW_IMPLS, SERVER_IMPLS

def test_common_options(out, *args):
    commands = [
        "quiver",
        "quiver-arrow",
        "quiver-bench",
        "quiver-launch",
        "quiver-server",
    ]

    for command in commands:
        call("{} --help", command, output=out)
        call("{} --version", command, output=out)

def test_quiver_arrow(out, home):
    call("quiver-arrow send q0 --init-only")
    call("quiver-arrow --init-only receive q0")

    for impl in ARROW_IMPLS:
        impl_file = join(home, "exec", "quiver-arrow-{}".format(impl))

        if not exists(impl_file):
            warn("No implementation at '{}'; skipping it", impl_file)
            continue

        call("quiver-arrow --impl {} --impl-info", impl, output=out)

def test_quiver_server(out, home):
    for impl in SERVER_IMPLS:
        if impl == "activemq" and which("activemq") is None:
            continue

        if impl == "artemis" and which("artemis") is None:
            continue

        if impl == "qpidd" and which("qpidd") is None:
            continue

        if impl == "qdrouterd" and which("qdrouterd") is None:
            continue

        call("quiver-server --impl {} --impl-info", impl, output=out)

        if impl == "activemq-artemis": continue # XXX Permissions problem

        port = random_port()
        url = "//127.0.0.1:{}/q0".format(port)
        ready_file = make_temp_file()

        with running_process("quiver-server --impl {} --ready-file {} {}", impl, ready_file, url, output=out):
            for i in range(30):
                if read(ready_file) == "ready\n":
                    break

                sleep(1)

            call("quiver {} -m 1", url, output=out)

def test_quiver_launch_client_server(out, url):
    call("quiver-launch {} --count 2 --options \"-m 1\" --verbose", url, output=out)

def test_quiver_launch_peer_to_peer(out):
    port = random_port()
    url = "//127.0.0.1:{}/q0".format(port)

    call("quiver-launch --sender-options=\"-m 1\" --receiver-options=\"-m 1 --server --passive\" {}", url, output=out)

def test_quiver_pair_client_server(out, url):
    # XXX full matrix

    call("quiver {} --arrow qpid-proton-python -m 1", url, output=out)
    call("quiver {} --arrow qpid-jms -m 1", url, output=out)
    call("quiver {} --arrow vertx-proton -m 1", url, output=out)

def test_quiver_pair_peer_to_peer(out):
    # XXX full matrix

    port = random_port()
    url = "//127.0.0.1:{}/q0".format(port)

    call("quiver {} --arrow rhea -m 1 --peer-to-peer", url, output=out)
    call("quiver {} --arrow qpid-proton-python -m 1 --peer-to-peer", url, output=out)

def test_quiver_bench(out):
    temp_dir = make_temp_dir()

    args = [
        "quiver-bench",
        "-m", "1",
        "--include-servers", "builtin",
        "--exclude-servers", "none",
        "--verbose",
        "--output", temp_dir,
    ]

    call(args, output=out)

def run_test(name, *args):
    sys.stdout.write("{:.<73} ".format(name + " "))
    sys.stdout.flush()

    namespace = globals()
    function = namespace["test_{}".format(name)]

    output_file = make_temp_file()

    try:
        with open(output_file, "w") as out:
            function(out, *args)
    except CalledProcessError:
        print("FAILED")

        for line in read_lines(output_file):
            eprint("> {}".format(line), end="")

        return 1

    print("PASSED")

    return 0

def main(home):
    set_message_threshold("error")

    parser = argparse.ArgumentParser()
    parser.add_argument("url", metavar="URL", nargs="?",
                        help="An AMQP message address to test against")

    args = parser.parse_args()

    failures = 0

    url = args.url
    server = None

    if url is None:
        port = random_port()
        url = "//127.0.0.1:{}/q0".format(port)
        server = start_process("quiver-server --quiet {}", url)
        wait_for_port(port)

    try:
        failures += run_test("common_options")
        failures += run_test("quiver_arrow", home)
        failures += run_test("quiver_server", home)
        failures += run_test("quiver_launch_client_server", url)
        failures += run_test("quiver_launch_peer_to_peer")
        failures += run_test("quiver_pair_client_server", url)
        failures += run_test("quiver_pair_peer_to_peer")
        failures += run_test("quiver_bench")
    finally:
        if server is not None:
            stop_process(server)

    if failures == 0:
        print("All tests passed")
    else:
        exit("Some tests failed")
