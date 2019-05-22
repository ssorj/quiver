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

import json as _json
import os as _os
import plano as _plano
import shlex as _shlex
import subprocess as _subprocess
import time as _time

from .arrow import _StatusSnapshot
from .common import *
from .common import __version__
from .common import _epilog_address_urls
from .common import _epilog_arrow_impls
from .common import _epilog_count_and_duration_formats

_description = """
Start a sender-receiver pair for a particular messaging address.

'quiver' is one of the Quiver tools for testing the performance of
message servers and APIs.
"""

_epilog = """
{_epilog_address_urls}

{_epilog_count_and_duration_formats}

{_epilog_arrow_impls}

example usage:
  $ qdrouterd &                   # Start a message server
  $ quiver q0                     # Start the test
""".format(**globals())

class QuiverPairCommand(Command):
    def __init__(self, home_dir):
        super(QuiverPairCommand, self).__init__(home_dir)

        self.parser.description = _description.lstrip()
        self.parser.epilog = _epilog.lstrip()

        self.parser.add_argument("url", metavar="ADDRESS-URL",
                                 help="The location of a message source or target")
        self.parser.add_argument("--output", metavar="DIR",
                                 help="Save output files to DIR")
        self.parser.add_argument("--arrow", metavar="IMPL", default=DEFAULT_ARROW_IMPL,
                                 help="Use IMPL to send and receive " \
                                 "(default {})".format(DEFAULT_ARROW_IMPL))
        self.parser.add_argument("--sender", metavar="IMPL",
                                 help="Use IMPL to send (default {})".format(DEFAULT_ARROW_IMPL))
        self.parser.add_argument("--receiver", metavar="IMPL",
                                 help="Use IMPL to receive (default {})".format(DEFAULT_ARROW_IMPL))
        self.parser.add_argument("--impl", metavar="IMPL",
                                 help="An alias for --arrow")
        self.parser.add_argument("--peer-to-peer", action="store_true",
                                 help="Connect the sender directly to the receiver in server mode")
        self.parser.add_argument("--cert", metavar="CERT.PEM",
                                 help="Certificate filename - used for client authentication")
        self.parser.add_argument("--key", metavar="PRIVATE-KEY.PEM",
                                 help="Private key filename - - used for client authentication")

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
        args = list()

        if self.duration == 0:
            args += ["--count", self.args.count]
        else:
            args += ["--duration", self.args.duration]

        args += [
            "--body-size", self.args.body_size,
            "--credit", self.args.credit,
            "--transaction-size", self.args.transaction_size,
            "--timeout", self.args.timeout,
        ]

        if self.durable:
            args += ["--durable"]

        if self.quiet:
            args += ["--quiet"]

        if self.verbose:
            args += ["--verbose"]

        if self.settlement:
            args += ["--settlement"]

        if self.args.cert and self.args.key:
            args += ["--key", self.args.key]
            args += ["--cert", self.args.cert]

        args += ["--output", self.output_dir]

        sender_args = ["quiver-arrow", "send", self.url, "--impl", self.sender_impl.name] + args
        receiver_args = ["quiver-arrow", "receive", self.url, "--impl", self.receiver_impl.name] + args

        if self.peer_to_peer:
            receiver_args += ["--server", "--passive"]

        self.start_time = now()

        #_os.environ["DEBUG"] = "*"
        receiver = _plano.start_process(receiver_args)
        #del _os.environ["DEBUG"]

        if self.peer_to_peer:
            _plano.wait_for_port(self.port, host=self.host)

        #_os.environ["PN_TRACE_FRM"] = "1"
        sender = _plano.start_process(sender_args)
        #del _os.environ["PN_TRACE_FRM"]

        try:
            if not self.quiet:
                self.print_status(sender, receiver)

            _plano.check_process(receiver)
            _plano.check_process(sender)
        except _plano.CalledProcessError as e:
            _plano.error(e)
        finally:
            _plano.stop_process(sender)
            _plano.stop_process(receiver)

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

                #print("S: {} R: {}".format(sline, rline))

                if sline is not None:
                    ssnap = _StatusSnapshot(self, None)
                    ssnap.unmarshal(sline)

                if rline is not None:
                    rsnap = _StatusSnapshot(self, None)
                    rsnap.unmarshal(rline)

                if rsnap is None:
                    continue

                if self.settlement and ssnap is None:
                    continue

                if i % 20 == 0:
                    self.print_status_headings()

                self.print_status_row(ssnap, rsnap)

                ssnap, rsnap = None, None
                i += 1

    column_groups = "{:-^53}  {:-^53}  {:-^18}"
    columns = "{:>8}  {:>13}  {:>10}  {:>7}  {:>7}  " \
              "{:>8}  {:>13}  {:>10}  {:>7}  {:>7}  " \
              "{:>8}  {:>8}"
    heading_row_1 = column_groups.format(" Sender ", " Receiver ", "Latency")
    heading_row_2 = columns.format \
        ("Time [s]", "Count [m]", "Rate [m/s]", "CPU [%]", "RSS [M]",
         "Time [s]", "Count [m]", "Rate [m/s]", "CPU [%]", "RSS [M]",
         "Rcv [ms]", "Stl [ms]")
    heading_row_3 = column_groups.format("", "", "")

    def print_status_headings(self):
        print(self.heading_row_1)
        print(self.heading_row_2)
        print(self.heading_row_3)

    def print_status_row(self, ssnap, rsnap):
        if ssnap is None:
            stime, scount, srate, scpu, srss = "-", "-", "-", "-", "-"
        else:
            stime = (ssnap.timestamp - self.start_time) / 1000000
            srate = ssnap.period_count / (ssnap.period / 1000000)
            scpu = (ssnap.period_cpu_time / ssnap.period) * 100000
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
            rtime = (rsnap.timestamp - self.start_time) / 1000000
            rrate = rsnap.period_count / (rsnap.period / 1000000)
            rcpu = (rsnap.period_cpu_time / rsnap.period) * 100000
            rrss = rsnap.rss / (1000 * 1024)

            rtime = "{:,.1f}".format(rtime)
            rcount = "{:,d}".format(rsnap.count)
            rrate = "{:,.0f}".format(rrate)
            rcpu = "{:,.0f}".format(rcpu)
            rrss = "{:,.1f}".format(rrss)

            latency = "{:,.0f}".format(rsnap.latency)
            slatency= "{:,.0f}".format(ssnap.latency) if self.settlement else ""

        row = self.columns.format(stime, scount, srate, scpu, srss,
                                  rtime, rcount, rrate, rcpu, rrss,
                                  latency, slatency)
        print(row)

    def print_summary(self):
        with open(_join(self.output_dir, "sender-summary.json")) as f:
            sender = _json.load(f)

        with open(_join(self.output_dir, "receiver-summary.json")) as f:
            receiver = _json.load(f)

        _print_heading("Configuration")

        _print_field("Sender", self.sender_impl.name)
        _print_field("Receiver", self.receiver_impl.name)
        _print_field("Address URL", self.url)
        _print_field("Output files", self.output_dir)

        if self.count != 0:
            _print_numeric_field("Count", self.count, _plano.plural("message", self.count))

        if self.duration != 0:
            _print_numeric_field("Duration", self.duration, _plano.plural("second", self.duration), "{:,.3f}")

        _print_numeric_field("Body size", self.body_size, _plano.plural("byte", self.body_size))
        _print_numeric_field("Credit window", self.credit_window, _plano.plural("message", self.credit_window))

        if self.transaction_size != 0:
            _print_numeric_field("Transaction size", self.transaction_size, _plano.plural("message", self.transaction_size))

        flags = list()

        if self.durable:
            flags.append("durable")

        if self.peer_to_peer:
            flags.append("peer-to-peer")

        if self.settlement:
            flags.append("settlement")

        if flags:
            _print_field("Flags", ", ".join(flags))

        _print_heading("Results")

        count = receiver["results"]["message_count"]

        start_time = sender["results"]["first_send_time"]
        end_time = receiver["results"]["last_receive_time"]

        duration = (end_time - start_time) / 1000000
        rate = None

        no_credit_events = sender["results"]["no_credit_events"]
        no_credit_duration = sender["results"]["no_credit_duration"]

        if duration > 0:
            rate = count / duration

        # XXX Sender and receiver CPU, RSS

        _print_numeric_field("Count", count, _plano.plural("message", self.count))
        _print_numeric_field("Duration", duration, "seconds", "{:,.1f}")
        _print_numeric_field("No Credit events", no_credit_events, _plano.plural("event", no_credit_events), "{:,.0f}")
        _print_numeric_field("No Credit duration", no_credit_duration, "uS", "{:,.0f}")
        _print_numeric_field("Sender rate", sender["results"]["message_rate"], "messages/s")
        _print_numeric_field("Receiver rate", receiver["results"]["message_rate"], "messages/s")
        _print_numeric_field("End-to-end rate", rate, "messages/s")

        print()
        print("Receive latencies by percentile:")
        print()

        _print_latency_fields("0%", receiver["results"]["latency_quartiles"][0],
                              "90.00%", receiver["results"]["latency_nines"][0])
        _print_latency_fields("25%", receiver["results"]["latency_quartiles"][1],
                              "99.00%", receiver["results"]["latency_nines"][1])
        _print_latency_fields("50%", receiver["results"]["latency_quartiles"][2],
                              "99.90%", receiver["results"]["latency_nines"][2])
        _print_latency_fields("100%", receiver["results"]["latency_quartiles"][4],
                              "99.99%", receiver["results"]["latency_nines"][3])

        if self.settlement and sender["results"]["latency_quartiles_settlement"] is not None:
            print()
            print("Settlement latencies by percentile:")
            print()

            _print_latency_fields("0%", sender["results"]["latency_quartiles_settlement"][0],
                                "90.00%", sender["results"]["latency_nines_settlement"][0])
            _print_latency_fields("25%", sender["results"]["latency_quartiles_settlement"][1],
                                "99.00%", sender["results"]["latency_nines_settlement"][1])
            _print_latency_fields("50%", sender["results"]["latency_quartiles_settlement"][2],
                                "99.90%", sender["results"]["latency_nines_settlement"][2])
            _print_latency_fields("100%", sender["results"]["latency_quartiles_settlement"][4],
                                "99.99%", sender["results"]["latency_nines_settlement"][3])

def _print_heading(name):
    print()
    print(name.upper())
    print()

def _print_field(name, value):
    name = "{} ".format(name)
    value = " {}".format(value)
    print("{:.<19}{:.>42}".format(name, value))

def _print_numeric_field(name, value, unit, fmt="{:,.0f}"):
    name = "{} ".format(name)

    if value is None:
        value = "-"
    elif fmt is not None:
        value = fmt.format(value)

    value = " {}".format(value)

    print("{:.<24}{:.>37} {}".format(name, value, unit))

def _print_latency_fields(lname, lvalue, rname, rvalue):
    lvalue = " {}".format(lvalue)
    rvalue = " {}".format(rvalue)
    print("{:>12} {:.>10} uS {:>12} {:.>10} uS".format(lname, lvalue, rname, rvalue))

def _read_line(file_):
    fpos = file_.tell()
    line = file_.readline()

    if line == b"":
        return None

    if not line.endswith(b"\n"):
        file_.seek(fpos)
        return None

    return line[:-1]

_join = _plano.join
