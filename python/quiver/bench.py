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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import with_statement

import argparse as _argparse
import os as _os
import plano as _plano
import shlex as _shlex
import subprocess as _subprocess
import time as _time
import traceback as _traceback

from .common import *
from .common import _install_sigterm_handler

_description = """
Benchmark message sender, receiver, and server combinations.

'quiver-bench' is one of the Quiver tools for testing the performance
of message servers and APIs.
"""

_epilog = """
The --senders, --receivers, and --servers arguments take a comma-
separated list of implementation names.  See `quiver-arrow --help` and
`quiver-server --help` to see the list of available implementations.
"""

class QuiverBenchCommand(Command):
    def __init__(self, home_dir):
        super(QuiverBenchCommand, self).__init__(home_dir)

        self.parser.description = _description.lstrip()
        self.parser.epilog = _epilog.lstrip()

        # XXX
        #self.parser.add_argument("--output", metavar="DIRECTORY",
        #                         help="Save output files to DIRECTORY")
        self.parser.add_argument("--senders", metavar="IMPLS",
                                 help="Test only senders in IMPLS")
        self.parser.add_argument("--receivers", metavar="IMPLS",
                                 help="Test only receivers in IMPLS")
        self.parser.add_argument("--servers", metavar="IMPLS",
                                 help="Test only servers in IMPLS")
        self.parser.add_argument("--client-server", action="store_true",
                                 help="Test only client-server mode")
        self.parser.add_argument("--peer-to-peer", action="store_true",
                                 help="Test only peer-to-peer mode")
        self.parser.add_argument("--matching-pairs", action="store_true",
                                 help="Test only matching senders and receivers")

        self.add_common_test_arguments()
        self.add_common_tool_arguments()

    def init(self):
        super(QuiverBenchCommand, self).init()

        prefix = _plano.program_name()
        datestamp = _time.strftime('%Y-%m-%d', _time.localtime())

        self.output_dir = "{}-{}".format(prefix, datestamp)

        _plano.remove(self.output_dir)
        _plano.make_dir(self.output_dir)

        self.client_server = True
        self.peer_to_peer = True

        if self.args.client_server:
            self.peer_to_peer = False

        if self.args.peer_to_peer:
            self.client_server = False

        self.matching_pairs = self.args.matching_pairs

        self.init_impl_attributes()
        self.init_common_test_attributes()
        self.init_common_tool_attributes()

        self.failures = list()

    def init_impl_attributes(self):
        self.sender_impls = list(ARROW_IMPLS)
        self.receiver_impls = list(ARROW_IMPLS)
        self.server_impls = list(SERVER_IMPLS)

        # XXX filter!
        # XXX check for impl availability

    def run(self):
        if self.client_server:
            for sender_impl in self.sender_impls:
                for receiver_impl in self.receiver_impls:
                    if self.matching_pairs:
                        if sender_impl != receiver_impl:
                            continue

                    for server_impl in self.server_impls:
                        if "activemq-artemis-jms" in (sender_impl, receiver_impl):
                            if server_impl != "activemq-artemis":
                                continue

                        if "activemq-jms" in (sender_impl, receiver_impl):
                            if server_impl not in ("activemq", "activemq-artemis"):
                                continue

                        self.run_test(sender_impl, receiver_impl, server_impl)

        if self.peer_to_peer:
            for sender_impl in self.sender_impls:
                if sender_impl in ("activemq-jms", "activemq-artemis-jms"):
                    continue

                for receiver_impl in self.receiver_impls:
                    if self.matching_pairs:
                        if sender_impl != receiver_impl:
                            continue

                    if receiver_impl not in PEER_TO_PEER_ARROW_IMPLS:
                        continue

                    self.run_test(sender_impl, receiver_impl, None)

        print("Test failures: {}".format(len(self.failures)))

        for failure in self.failures:
            print(failure) # Need summary

    def run_test(self, sender_impl, receiver_impl, server_impl):
        if server_impl is None:
            summary = "{} -> {} ".format(sender_impl, receiver_impl)
            test_dir = _plano.join(self.output_dir, sender_impl, receiver_impl, "peer-to-peer")
        else:
            summary = "{} -> {} -> {} ".format(sender_impl, server_impl, receiver_impl)
            test_dir = _plano.join(self.output_dir, sender_impl, receiver_impl, server_impl)

        print("{:.<113} ".format(summary), end="")

        _plano.flush()

        test_data_dir = _plano.join(test_dir, "data")
        test_output_file = _plano.join(test_dir, "output.txt")
        test_status_file = _plano.join(test_dir, "status.txt")

        test_command = [
            "quiver", "//127.0.0.1/q0",
            "--sender", sender_impl,
            "--receiver", receiver_impl,
            "--output", test_data_dir,
            "--messages", self.args.messages,
            "--body-size", self.args.body_size,
            "--credit", self.args.credit,
            "--timeout", self.args.timeout,
        ]

        if server_impl is None:
            test_command.append("--peer-to-peer")

        test_command = " ".join(test_command)

        server = None
        server_output_file = _plano.join(test_dir, "server-output.txt")
        server_ready_file = _plano.make_temp_file()

        server_command = [
            "quiver-server", "//127.0.0.1/q0",
            "--impl", server_impl,
            "--ready-file", server_ready_file,
            "--verbose",
        ]

        server_command = " ".join(server_command)

        _plano.make_dir(test_dir)

        with open(server_output_file, "w") as sf:
            with open(test_output_file, "w") as tf:
                try:
                    if server_impl is not None:
                        server = _plano.start_process(server_command, stdout=sf, stderr=sf)

                        for i in range(30):
                            if _plano.read(server_ready_file) == "ready\n":
                                break

                            _plano.sleep(1)
                        else:
                            raise _Timeout("Timed out waiting for server to be ready")

                    _plano.call(test_command, stdout=tf, stderr=tf)

                    _plano.write(test_status_file, "PASSED")

                    print("PASSED")
                except KeyboardInterrupt:
                    raise
                except (_plano.CalledProcessError, _Timeout) as e:
                    self.failures.append(str(e))

                    _plano.write(test_status_file, "FAILED: {}".format(str(e)))

                    print("FAILED")

                    if self.verbose:
                        # XXX Record the result in this format

                        print("--- Error message ---")
                        print("> {}".format(str(e)))
                        print("--- Test command ---")
                        print("> {}".format(test_command))
                        print("--- Test output ---")

                        for line in _plano.read_lines(test_output_file):
                            print("> {}".format(line), end="")

                        if server_impl is not None:
                            print("--- Server command ---")
                            print("> {}".format(server_command))
                            print("--- Server output ---")

                            for line in _plano.read_lines(server_output_file):
                                print("> {}".format(line), end="")
                except:
                    _traceback.print_exc()
                finally:
                    _plano.flush()

                    if server is not None:
                        _plano.stop_process(server)

class _Timeout(Exception):
    pass
