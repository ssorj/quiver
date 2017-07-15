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

def test_quiver_peer_to_peer(out):
    port = random_port()
    url = "//127.0.0.1:{}/q0".format(port)
    
    call("quiver {} --arrow rhea -m 1 --peer-to-peer", url, output=out)
    call("quiver {} --arrow qpid-proton-python -m 1 --peer-to-peer", url, output=out)

def test_quiver_client_server(out, url):
    call("quiver {} -m 10k --verbose", url, output=out)

    # XXX full matrix
    
    call("quiver {} --arrow qpid-jms -m 1 --durable", url, output=out)
    call("quiver {} --arrow vertx-proton -m 1", url, output=out)

def run_test(name, *args):
    sys.stdout.write("{:.<73} ".format(name + " "))

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

def main():
    set_message_threshold("warn")

    parser = argparse.ArgumentParser()
    parser.add_argument("url", metavar="ADDRESS-URL", nargs="?",
                        help="An AMQP message address to test against")

    args = parser.parse_args()

    failures = 0
    failures += run_test("common_options")
    failures += run_test("quiver_peer_to_peer")

    url = args.url
    server = None

    if url is None:
        port = random_port()
        url = "//127.0.0.1:{}/q0".format(port)
        server = start_process("quiver-server --quiet {}", url)

    try:
        failures += run_test("quiver_client_server", url)
    finally:
        if server is not None:
            stop_process(server)

    if failures == 0:
        print("All tests passed")
    else:
        exit("Some tests failed")
