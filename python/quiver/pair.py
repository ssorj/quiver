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

import os as _os
import plano as _plano
import shlex as _shlex
import subprocess as _subprocess
import time as _time

from .arrow import _StatusSnapshot
from .common import *
from .common import __version__
from .common import _epilog_urls
from .common import _epilog_arrow_impls
from .common import _epilog_count_and_duration_formats

_description = """
Start a sender-receiver pair for a particular messaging address.

'quiver' is one of the Quiver tools for testing the performance of
message servers and APIs.
"""

_epilog = """
{_epilog_urls}

{_epilog_count_and_duration_formats}

{_epilog_arrow_impls}

example peer-to-peer usage:
  $ quiver                        # Run the test using the default C arrow

example client-server usage:
  $ qdrouterd &                   # Start a server listening on localhost
  $ quiver q0                     # Run the test
""".format(**globals())

class QuiverPairCommand(Command):
    def __init__(self, home_dir):
        super(QuiverPairCommand, self).__init__(home_dir)

        self.parser.description = _description.lstrip()
        self.parser.epilog = _epilog.lstrip()

        self.parser.add_argument("url", metavar="URL", nargs="?",
                                 help="The location of a message source or target "
                                 "(if not set, quiver runs in peer-to-peer mode)")
        self.parser.add_argument("--output", metavar="DIR",
                                 help="Save output files to DIR")
        self.parser.add_argument("--impl", metavar="IMPL", default=DEFAULT_ARROW_IMPL,
                                 help="Use IMPL to send and receive " \
                                 "(default {})".format(DEFAULT_ARROW_IMPL))
        self.parser.add_argument("--sender", metavar="IMPL",
                                 help="Use IMPL to send (default {})".format(DEFAULT_ARROW_IMPL))
        self.parser.add_argument("--receiver", metavar="IMPL",
                                 help="Use IMPL to receive (default {})".format(DEFAULT_ARROW_IMPL))

        self.add_common_test_arguments()
        self.add_common_tool_arguments()
        self.add_common_tls_arguments()

        self.start_time = None

    def init(self):
        super(QuiverPairCommand, self).init()

        impl = self.args.impl

        self.sender_impl = require_impl(self.args.sender, impl)
        self.receiver_impl = require_impl(self.args.receiver, impl)

        self.init_url_attributes()
        self.init_output_dir()
        self.init_common_test_attributes()
        self.init_common_tool_attributes()

    def run(self):
        args = [
            "--duration", self.args.duration,
            "--count", self.args.count,
            "--rate", self.args.rate,
            "--body-size", self.args.body_size,
            "--credit", self.args.credit,
            "--transaction-size", self.args.transaction_size,
            "--timeout", self.args.timeout,
        ]

        if self.durable:
            args += ["--durable"]

        if self.set_message_id:
            args += ["--set-message-id"]

        if self.quiet:
            args += ["--quiet"]

        if self.verbose:
            args += ["--verbose"]

        if self.args.cert and self.args.key:
            args += ["--key", self.args.key]
            args += ["--cert", self.args.cert]

        args += ["--output", self.output_dir]

        sender_args = ["quiver-arrow", "send", self.url, "--impl", self.sender_impl.name] + args
        receiver_args = ["quiver-arrow", "receive", self.url, "--impl", self.receiver_impl.name] + args

        if self.args.url is None:
            receiver_args += ["--server", "--passive"]

        self.start_time = now()

        # with working_env(PN_LOG=frame, DEBUG="*"):
        receiver = _plano.start(receiver_args)

        if self.args.url is None:
            _plano.await_port(self.port, host=self.host)

        # with working_env(PN_LOG=frame, DEBUG="*"):
        sender = _plano.start(sender_args)

        try:
            if not self.quiet:
                self.print_status(sender, receiver)

            _plano.wait(receiver, check=True)
            _plano.wait(sender, check=True)
        except _plano.PlanoProcessError as e:
            _plano.error(e)
        finally:
            _plano.stop(sender)
            _plano.stop(receiver)

        if (sender.exit_code, receiver.exit_code) != (0, 0):
            _plano.exit(1)

        if not self.quiet:
            self.print_summary()

    def print_status(self, sender, receiver):
        sender_snaps = _plano.join(self.output_dir, "sender-snapshots.csv")
        receiver_snaps = _plano.join(self.output_dir, "receiver-snapshots.csv")

        _plano.touch(sender_snaps)
        _plano.touch(receiver_snaps)

        ssnap, rsnap = None, None
        i = 0

        with open(sender_snaps, "rb") as fs, open(receiver_snaps, "rb") as fr:
            while receiver.poll() == None:
                _time.sleep(1)

                sline = _read_line(fs)
                rline = _read_line(fr)

                # print("S: {} R: {}".format(sline, rline))

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
        sender = _plano.read_json(_plano.join(self.output_dir, "sender-summary.json"))
        receiver = _plano.read_json(_plano.join(self.output_dir, "receiver-summary.json"))

        print_heading("Configuration")

        print_field("Sender", self.sender_impl.name)
        print_field("Receiver", self.receiver_impl.name)
        print_field("URL", self.url)
        print_field("Output files", self.output_dir)

        if self.count != 0:
            print_numeric_field("Count", self.count, _plano.plural("message", self.count))

        if self.duration != 0:
            print_numeric_field("Duration", self.duration, _plano.plural("second", self.duration))

        print_numeric_field("Body size", self.body_size, _plano.plural("byte", self.body_size))
        print_numeric_field("Credit window", self.credit_window, _plano.plural("message", self.credit_window))

        if self.transaction_size != 0:
            print_numeric_field("Transaction size", self.transaction_size, _plano.plural("message", self.transaction_size))

        if self.durable:
            print_field("Durable", "Yes")

        if self.set_message_id:
            print_field("Set message ID", "Yes")

        print_heading("Results")

        count = receiver["results"]["message_count"]

        start_time = sender["results"]["first_send_time"]
        end_time = receiver["results"]["last_receive_time"]

        duration = (end_time - start_time) / 1000
        rate = None

        if duration > 0:
            rate = count / duration

        # XXX Sender and receiver CPU, RSS

        print_numeric_field("Count", count, _plano.plural("message", self.count))
        print_numeric_field("Duration", duration, "seconds", "{:,.1f}")
        print_numeric_field("Sender rate", sender["results"]["message_rate"], "messages/s")
        print_numeric_field("Receiver rate", receiver["results"]["message_rate"], "messages/s")
        print_numeric_field("End-to-end rate", rate, "messages/s")

        print()
        print("Latencies by percentile:")
        print()

        print_latency_fields("0%", receiver["results"]["latency_quartiles"][0],
                             "90.00%", receiver["results"]["latency_nines"][0])
        print_latency_fields("25%", receiver["results"]["latency_quartiles"][1],
                             "99.00%", receiver["results"]["latency_nines"][1])
        print_latency_fields("50%", receiver["results"]["latency_quartiles"][2],
                             "99.90%", receiver["results"]["latency_nines"][2])
        print_latency_fields("100%", receiver["results"]["latency_quartiles"][4],
                             "99.99%", receiver["results"]["latency_nines"][3])

def _read_line(file_):
    fpos = file_.tell()
    line = file_.readline()

    if line == b"":
        return None

    if not line.endswith(b"\n"):
        file_.seek(fpos)
        return None

    return line[:-1]
