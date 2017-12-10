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

import json as _json
import os as _os
import plano as _plano
import shlex as _shlex
import subprocess as _subprocess
import time as _time

from .arrow import _StatusSnapshot
from .common import *
from .common import __version__

_description = """
Start a sender-receiver pair for a particular messaging address.

'quiver' is one of the Quiver tools for testing the performance of
message servers and APIs.
"""

_epilog = """
URLs:
  [amqp://DOMAIN/]PATH            The default domain is 'localhost'
  amqp://example.net/jobs
  amqp://10.0.0.10:5672/jobs/alpha
  amqp://localhost/q0
  q0

implementations:
  activemq-artemis-jms            Client mode only; requires Artemis server
  activemq-jms                    Client mode only; ActiveMQ or Artemis server
  qpid-jms [jms]                  Client mode only
  qpid-messaging-cpp              Client mode only
  qpid-messaging-python           Client mode only
  qpid-proton-c [c]
  qpid-proton-cpp [cpp]
  qpid-proton-python [python]
  rhea [javascript]
  vertx-proton [java]             Client mode only

example usage:
  $ qdrouterd &                   # Start a message server
  $ quiver q0                     # Start test
"""

class QuiverPairCommand(Command):
    def __init__(self, home_dir):
        super(QuiverPairCommand, self).__init__(home_dir)

        self.parser.description = _description.lstrip()
        self.parser.epilog = _epilog.lstrip()

        self.parser.add_argument("url", metavar="URL",
                                 help="The location of a message queue")
        self.parser.add_argument("--output", metavar="DIR",
                                 help="Save output files to DIR")
        self.parser.add_argument("--arrow", metavar="IMPL", default=DEFAULT_ARROW_IMPL,
                                 help="Use IMPL to send and receive")
        self.parser.add_argument("--sender", metavar="IMPL",
                                 help="Use IMPL to send")
        self.parser.add_argument("--receiver", metavar="IMPL",
                                 help="Use IMPL to receive")
        self.parser.add_argument("--impl", metavar="IMPL",
                                 help="An alias for --arrow")
        self.parser.add_argument("--peer-to-peer", action="store_true",
                                 help="Test peer-to-peer mode")

        self.add_common_test_arguments()
        self.add_common_tool_arguments()

        self.start_time = None

    def init(self):
        super(QuiverPairCommand, self).init()

        arrow = self.args.arrow

        if self.args.impl is not None:
            arrow = self.args.impl

        self.sender_impl = require_impl(self.args.sender, arrow)
        self.receiver_impl = require_impl(self.args.receiver, arrow)
        self.peer_to_peer = self.args.peer_to_peer

        self.init_url_attributes()
        self.init_output_dir()
        self.init_common_test_attributes()
        self.init_common_tool_attributes()

    def run(self):
        args = [
            self.url,
            "--messages", self.args.messages,
            "--body-size", self.args.body_size,
            "--credit", self.args.credit,
            "--transaction-size", self.args.transaction_size,
            "--timeout", self.args.timeout,
            "--output", self.output_dir,
        ]

        if self.durable:
            args += ["--durable"]

        if self.quiet:
            args += ["--quiet"]

        if self.verbose:
            args += ["--verbose"]

        sender_args = ["quiver-arrow", "send", "--impl", self.sender_impl.name] + args
        receiver_args = ["quiver-arrow", "receive", "--impl", self.receiver_impl.name] + args

        if self.peer_to_peer:
            receiver_args += ["--server", "--passive"]

        self.start_time = now()

        receiver = _plano.start_process(receiver_args)

        if self.peer_to_peer:
            _plano.wait_for_port(self.port, host=self.host)

        sender = _plano.start_process(sender_args)

        try:
            if not self.quiet:
                self.print_status(sender, receiver)

            _plano.wait_for_process(sender)
            _plano.wait_for_process(receiver)
        except:
            _plano.stop_process(sender)
            _plano.stop_process(receiver)

            raise

        if (sender.returncode, receiver.returncode) != (0, 0):
            _plano.exit(1)

        if not self.quiet:
            self.print_summary()

    def print_status(self, sender, receiver):
        sender_snaps = _join(self.output_dir, "sender-snapshots.csv")
        receiver_snaps = _join(self.output_dir, "receiver-snapshots.csv")

        _plano.touch(sender_snaps)
        _plano.touch(receiver_snaps)

        ssnap, rsnap = None, None
        i = 0

        with open(sender_snaps, "rb") as fs, open(receiver_snaps, "rb") as fr:
            while receiver.poll() == None:
                _time.sleep(1)

                sline = _read_line(fs)
                rline = _read_line(fr)

                #print("S: {:60} R: {}".format(sline, rline))

                if sline is not None:
                    ssnap = _StatusSnapshot(self, None)
                    ssnap.unmarshal(sline)

                if rline is not None:
                    rsnap = _StatusSnapshot(self, None)
                    rsnap.unmarshal(rline)

                if rsnap is None:
                    continue

                if i % 20 == 0:
                    self.print_status_headings()

                self.print_status_row(ssnap, rsnap)

                ssnap, rsnap = None, None
                i += 1

    column_groups = "{:-^53}  {:-^53}  {:-^8}"
    columns = "{:>8}  {:>13}  {:>10}  {:>7}  {:>7}  " \
              "{:>8}  {:>13}  {:>10}  {:>7}  {:>7}  " \
              "{:>8}"
    heading_row_1 = column_groups.format(" Sender ", " Receiver ", "")
    heading_row_2 = columns.format \
        ("Time [s]", "Count [m]", "Rate [m/s]", "CPU [%]", "RSS [M]",
         "Time [s]", "Count [m]", "Rate [m/s]", "CPU [%]", "RSS [M]",
         "Lat [ms]")
    heading_row_3 = column_groups.format("", "", "")

    def print_status_headings(self):
        print(self.heading_row_1)
        print(self.heading_row_2)
        print(self.heading_row_3)

    def print_status_row(self, ssnap, rsnap):
        if ssnap is None:
            stime, scount, srate, scpu, srss = "-", "-", "-", "-", "-"
        else:
            stime = (ssnap.timestamp - self.start_time) / 1000
            srate = ssnap.period_count / (ssnap.period / 1000)
            scpu = (ssnap.period_cpu_time / ssnap.period) * 100
            srss = ssnap.rss / (1000 * 1024)

            stime = "{:,.1f}".format(stime)
            scount = "{:,d}".format(ssnap.count)
            srate = "{:,.0f}".format(srate)
            scpu = "{:,.0f}".format(scpu)
            srss = "{:,.1f}".format(srss)

        if rsnap is None:
            rtime, rcount, rrate, rcpu, rrss = "-", "-", "-", "-", "-"
            latency = "-"
        else:
            rtime = (rsnap.timestamp - self.start_time) / 1000
            rrate = rsnap.period_count / (rsnap.period / 1000)
            rcpu = (rsnap.period_cpu_time / rsnap.period) * 100
            rrss = rsnap.rss / (1000 * 1024)

            rtime = "{:,.1f}".format(rtime)
            rcount = "{:,d}".format(rsnap.count)
            rrate = "{:,.0f}".format(rrate)
            rcpu = "{:,.0f}".format(rcpu)
            rrss = "{:,.1f}".format(rrss)

            latency = "{:,.0f}".format(rsnap.latency)

        row = self.columns.format(stime, scount, srate, scpu, srss,
                                  rtime, rcount, rrate, rcpu, rrss,
                                  latency)
        print(row)

    def print_summary(self):
        with open(_join(self.output_dir, "sender-summary.json")) as f:
            sender = _json.load(f)

        with open(_join(self.output_dir, "receiver-summary.json")) as f:
            receiver = _json.load(f)

        print("-" * 80)

        # XXX Get impl info from json config of arrow output

        v = "{} {} ({})".format(self.args.impl, self.url, self.output_dir)
        print("Subject: {}".format(v))

        _print_numeric_field("Messages", self.messages, "messages")
        _print_numeric_field("Body size", self.body_size, "bytes")
        _print_numeric_field("Credit window", self.credit_window, "messages")

        start_time = sender["results"]["first_send_time"]
        end_time = receiver["results"]["last_receive_time"]
        duration = (end_time - start_time) / 1000
        rate = None

        if duration > 0:
            rate = receiver["results"]["message_count"] / duration

        # XXX Sender and receiver CPU, RSS

        _print_numeric_field("Duration", duration, "s", "{:,.1f}")
        v = sender["results"]["message_rate"]
        _print_numeric_field("Sender rate", v, "messages/s")
        v = receiver["results"]["message_rate"]
        _print_numeric_field("Receiver rate", v, "messages/s")
        _print_numeric_field("End-to-end rate", rate, "messages/s")

        print("Latency:")

        v = receiver["results"]["latency_quartiles"][0]
        _print_numeric_field("    0%", v, "ms", "{:,.0f}")
        v = receiver["results"]["latency_quartiles"][1]
        _print_numeric_field("   25%", v, "ms", "{:,.0f}")
        v = receiver["results"]["latency_quartiles"][2]
        _print_numeric_field("   50%", v, "ms", "{:,.0f}")
        v = receiver["results"]["latency_nines"][0]
        _print_numeric_field("   90%", v, "ms", "{:,.0f}")
        v = receiver["results"]["latency_nines"][1]
        _print_numeric_field("   99%", v, "ms", "{:,.0f}")
        v = receiver["results"]["latency_nines"][2]
        _print_numeric_field("   99.9%", v, "ms", "{:,.0f}")
        v = receiver["results"]["latency_nines"][3]
        _print_numeric_field("   99.99%", v, "ms", "{:,.0f}")
        v = receiver["results"]["latency_nines"][4]
        _print_numeric_field("   99.999%", v, "ms", "{:,.0f}")
        v = receiver["results"]["latency_quartiles"][4]
        _print_numeric_field("  100%", v, "ms", "{:,.0f}")

        print("-" * 80)

def _print_numeric_field(name, value, unit, fmt="{:,.0f}"):
    name = "{}:".format(name)

    if value is None:
        value = "-"
    elif fmt is not None:
        value = fmt.format(value)

    print("{:<28} {:>28} {}".format(name, value, unit))

def _read_line(file_):
    fpos = file_.tell()
    line = file_.readline()

    if line == "" or line[-1] != b"\n":
        file_.seek(fpos)
        return

    return line[:-1]

_join = _plano.join
