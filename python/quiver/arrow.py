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

import argparse as _argparse
import json as _json
import numpy as _numpy
import os as _os
import plano as _plano
import resource as _resource
import shlex as _shlex
import subprocess as _subprocess
import time as _time

from .common import *
from .common import __version__
from .common import _epilog_urls
from .common import _epilog_arrow_impls
from .common import _epilog_count_and_duration_formats
from .common import _urlparse

_description = """
Send or receive a set number of messages as fast as possible using a
single connection.

'quiver-arrow' is one of the Quiver tools for testing the performance
of message servers and APIs.
"""

_epilog = """
operations:
  send                  Send messages
  receive               Receive messages

{_epilog_urls}

{_epilog_count_and_duration_formats}

{_epilog_arrow_impls}

server and passive modes:
  By default quiver-arrow operates in client and active modes, meaning
  that it creates an outbound connection to a server and actively
  initiates creation of the protocol entities (sessions and links)
  required for communication.  The --server option tells quiver-arrow
  to instead listen for and accept incoming connections.  The
  --passive option tells it to receive and confirm incoming requests
  for new protocol entities but not to create them itself.

example usage:
  $ qdrouterd &                   # Start a message server
  $ quiver-arrow receive q0 &     # Start receiving
  $ quiver-arrow send q0          # Start sending
""".format(**globals())

class QuiverArrowCommand(Command):
    def __init__(self, home_dir):
        super(QuiverArrowCommand, self).__init__(home_dir)

        self.parser.description = _description.lstrip()
        self.parser.epilog = _epilog.lstrip()

        self.parser.add_argument("operation", metavar="OPERATION",
                                 choices=["send", "receive"],
                                 help="Either 'send' or 'receive'")
        self.parser.add_argument("url", metavar="URL",
                                 help="The location of a message source or target")
        self.parser.add_argument("--output", metavar="DIR",
                                 help="Save output files to DIR")
        self.parser.add_argument("--impl", metavar="IMPL", default=DEFAULT_ARROW_IMPL,
                                 help="Use IMPL to send and receive " \
                                 "(default {})".format(DEFAULT_ARROW_IMPL))
        self.parser.add_argument("--summary", action="store_true",
                                 help="Print the configuration and results to the console")
        self.parser.add_argument("--info", action="store_true",
                                 help="Print implementation details and exit")
        self.parser.add_argument("--id", metavar="ID",
                                 help="Use ID as the client or server identity")
        self.parser.add_argument("--server", action="store_true",
                                 help="Operate in server mode")
        self.parser.add_argument("--passive", action="store_true",
                                 help="Operate in passive mode")
        self.parser.add_argument("--prelude", metavar="PRELUDE", default="",
                                 help="Commands to precede the implementation invocation")

        self.add_common_test_arguments()
        self.add_common_tool_arguments()
        self.add_common_tls_arguments()

    def init(self):
        self.intercept_info_request(DEFAULT_ARROW_IMPL)

        super(QuiverArrowCommand, self).init()

        self.operation = self.args.operation
        self.impl = require_impl(self.args.impl)
        self.id_ = self.args.id
        self.connection_mode = "client"
        self.channel_mode = "active"
        self.prelude = _shlex.split(self.args.prelude)

        if self.operation == "send":
            self.role = "sender"
        elif self.operation == "receive":
            self.role = "receiver"
        else:
            raise Exception()

        if self.id_ is None:
            self.id_ = "quiver-{}-{}".format(self.role, _plano.get_unique_id(4))

        if self.args.server:
            self.connection_mode = "server"

        if self.args.passive:
            self.channel_mode = "passive"

        self.cert = self.args.cert
        self.key = self.args.key

        self.init_url_attributes()
        self.init_common_test_attributes()
        self.init_common_tool_attributes()
        self.init_output_dir()

        if _urlparse(self.url).port is None:
            if self.impl.name in ("activemq-artemis-jms"):
                self.port = "61616"

        self.snapshots_file = _join(self.output_dir, "{}-snapshots.csv".format(self.role))
        self.summary_file = _join(self.output_dir, "{}-summary.json".format(self.role))
        self.transfers_file = _join(self.output_dir, "{}-transfers.csv".format(self.role))

        self.start_time = None
        self.timeout_checkpoint = None

        self.first_send_time = None
        self.last_send_time = None
        self.first_receive_time = None
        self.last_receive_time = None
        self.message_count = None
        self.message_rate = None
        self.latency_average = None
        self.latency_quartiles = None
        self.latency_nines = None

    def run(self):
        args = self.prelude + [
            self.impl.file,
            "connection-mode={}".format(self.connection_mode),
            "channel-mode={}".format(self.channel_mode),
            "operation={}".format(self.operation),
            "id={}".format(self.id_),
            "scheme={}".format(self.scheme),
            "host={}".format(self.host),
            "port={}".format(self.port),
            "path={}".format(self.path),
            "duration={}".format(self.duration),
            "count={}".format(self.count),
            "rate={}".format(self.rate),
            "body-size={}".format(self.body_size),
            "credit-window={}".format(self.credit_window),
            "transaction-size={}".format(self.transaction_size),
            "durable={}".format(1 if self.durable else 0),
            "set-message-id={}".format(1 if self.set_message_id else 0),
        ]

        if self.username:
            args.append("username={}".format(self.username))

        if self.password:
            args.append("password={}".format(self.password))

        if self.args.cert and self.args.key:
            args.append("key={}".format(self.key))
            args.append("cert={}".format(self.cert))

        with open(self.transfers_file, "wb") as fout:
            if self.verbose:
                with _plano.working_env(QUIVER_VERBOSE=1):
                    proc = _plano.start(args, stdout=fout)
            else:
                proc = _plano.start(args, stdout=fout)

            try:
                self.monitor_subprocess(proc)
            except:
                _plano.stop(proc)
                raise

            if proc.returncode != 0:
                raise CommandError("{} exited with code {}", self.role, proc.returncode)

        if _plano.get_file_size(self.transfers_file) == 0:
            raise CommandError("No transfers")

        self.compute_results()
        self.save_summary()

        if _plano.exists("{}.zst".format(self.transfers_file)):
            _plano.remove("{}.zst".format(self.transfers_file))

        _plano.run(f"zstd --fast --quiet -T0 --rm -f {self.transfers_file}")

        if (self.args.summary):
            self.print_summary()

    def monitor_subprocess(self, proc):
        snap = _StatusSnapshot(self, None)
        snap.timestamp = now()

        self.start_time = snap.timestamp
        self.timeout_checkpoint = snap

        sleep = 2.0

        with open(self.transfers_file, "rb") as fin:
            with open(self.snapshots_file, "ab") as fsnaps:
                while proc.poll() is None:
                    _time.sleep(sleep)

                    period_start = _time.time()

                    snap.previous = None
                    snap = _StatusSnapshot(self, snap)
                    snap.capture(fin, proc)

                    fsnaps.write(snap.marshal())
                    fsnaps.flush()

                    self.check_timeout(snap)

                    period = _time.time() - period_start
                    sleep = max(1.0, 2.0 - period)

    def check_timeout(self, snap):
        checkpoint = self.timeout_checkpoint
        since = (snap.timestamp - checkpoint.timestamp) / 1000

        # print("check_timeout", snap.count, "==", checkpoint.count, "and", since, ">", self.timeout)

        if snap.count == checkpoint.count and since > self.timeout:
            raise CommandError("{} timed out", self.role)

        if snap.count > checkpoint.count:
            self.timeout_checkpoint = snap

    def compute_results(self):
        dtype = [("send_time", _numpy.uint64), ("receive_time", _numpy.uint64)]
        transfers = _numpy.fromiter(self.read_transfers(), dtype=dtype)

        self.message_count = len(transfers)

        if self.message_count == 0:
            return

        if self.operation == "send":
            self.first_send_time = int(transfers[0]["send_time"])
            self.last_send_time = int(transfers[-1]["send_time"])

            duration = (self.last_send_time - self.first_send_time) / 1000
        elif self.operation == "receive":
            self.first_receive_time = int(transfers[0]["receive_time"])
            self.last_receive_time = int(transfers[-1]["receive_time"])

            duration = (self.last_receive_time - self.first_receive_time) / 1000

            self.compute_latencies(transfers)
        else:
            raise Exception()

        if duration > 0:
            self.message_rate = int(round(self.message_count / duration))

    def read_transfers(self):
        with open(self.transfers_file, "rb") as f:
            for line in f:
                try:
                    send_time, receive_time = line.split(b",", 1)
                    yield send_time, receive_time
                except ValueError as e:
                    _plano.error("Failed to parse line '{}': {}", line, e)
                    continue

    def compute_latencies(self, transfers):
        latencies = transfers["receive_time"] - transfers["send_time"]
        q = 0, 25, 50, 75, 100, 90, 99, 99.9, 99.99, 99.999
        percentiles = _numpy.percentile(latencies, q)
        percentiles = [int(x) for x in percentiles]

        self.latency_average = _numpy.mean(latencies)
        self.latency_quartiles = percentiles[:5]
        self.latency_nines = percentiles[5:]

    def save_summary(self):
        props = {
            "config": {
                "impl": self.impl.name,
                "url": self.url,
                "output_dir": self.output_dir,
                "timeout": self.timeout,
                "connection_mode": self.connection_mode,
                "channel_mode": self.channel_mode,
                "operation": self.operation,
                "id": self.id_,
                "host": self.host,
                "port": self.port,
                "path": self.path,
                "duration": self.duration,
                "count": self.count,
                "rate": self.rate,
                "body_size": self.body_size,
                "credit_window": self.credit_window,
                "transaction_size": self.transaction_size,
                "durable": self.durable,
            },
            "results": {
                "first_send_time": self.first_send_time,
                "last_send_time": self.last_send_time,
                "first_receive_time": self.first_receive_time,
                "last_receive_time": self.last_receive_time,
                "message_count": self.message_count,
                "message_rate": self.message_rate,
                "latency_average": self.latency_average,
                "latency_quartiles": self.latency_quartiles,
                "latency_nines": self.latency_nines,
            },
        }

        with open(self.summary_file, "w") as f:
            _json.dump(props, f, indent=2)

    def print_summary(self):
        with open(self.summary_file) as f:
            arrow = _json.load(f)

        print_heading("Configuration")

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

        print_heading("Results")

        if self.operation == "send":
            start_time = arrow["results"]["first_send_time"]
            end_time = arrow["results"]["last_send_time"]
        elif self.operation == "receive":
            start_time = arrow["results"]["first_receive_time"]
            end_time = arrow["results"]["last_receive_time"]
        else:
            raise Exception()

        count = arrow["results"]["message_count"]
        duration = (end_time - start_time) / 1000

        print_numeric_field("Count", count, _plano.plural("message", self.count))
        print_numeric_field("Duration", duration, "seconds", "{:,.1f}")
        print_numeric_field("Message rate", arrow["results"]["message_rate"], "messages/s")

        if self.operation == "receive":
            print()
            print("Latencies by percentile:")
            print()

            print_latency_fields("0%", arrow["results"]["latency_quartiles"][0],
                                 "90.00%", arrow["results"]["latency_nines"][0])
            print_latency_fields("25%", arrow["results"]["latency_quartiles"][1],
                                 "99.00%", arrow["results"]["latency_nines"][1])
            print_latency_fields("50%", arrow["results"]["latency_quartiles"][2],
                                 "99.90%", arrow["results"]["latency_nines"][2])
            print_latency_fields("100%", arrow["results"]["latency_quartiles"][4],
                                 "99.99%", arrow["results"]["latency_nines"][3])

class _StatusSnapshot:
    def __init__(self, command, previous):
        self.command = command
        self.previous = previous

        self.timestamp = 0
        self.period = 0

        self.count = 0
        self.period_count = 0
        self.latency = 0

        self.cpu_time = 0
        self.period_cpu_time = 0
        self.rss = 0

    def capture(self, transfers_file, proc):
        assert self.previous is not None

        self.timestamp = now()
        self.period = self.timestamp - self.previous.timestamp

        self.capture_transfers(transfers_file)
        self.capture_proc_info(proc)

    def capture_transfers(self, transfers_file):
        transfers = list()
        sample = 100
        count = 0

        # Skip the first line since it may be incomplete
        for line in enumerate(transfers_file):
            break

        for count, line in enumerate(transfers_file):
            if count % sample != 0:
                continue

            if not line.endswith(b"\n"):
                continue

            try:
                send_time, receive_time = line.split(b",", 1)
                record = int(send_time), int(receive_time)
            except ValueError:
                continue

            transfers.append(record)

        self.period_count = count
        self.count = self.previous.count + self.period_count

        if self.period_count > 0 and self.command.operation == "receive":
            latencies = [receive_time - send_time for send_time, receive_time in transfers]

            if latencies:
                self.latency = int(_numpy.mean(latencies))

    def capture_proc_info(self, proc):
        proc_file = _join("/", "proc", str(proc.pid), "stat")

        try:
            with open(proc_file, "r") as f:
                line = f.read()
        except IOError:
            return

        fields = line.split()

        self.cpu_time = int(sum(map(int, fields[13:17])) / _ticks_per_ms)
        self.period_cpu_time = self.cpu_time

        if self.previous is not None:
            self.period_cpu_time = self.cpu_time - self.previous.cpu_time

        self.rss = int(fields[23]) * _page_size

    def marshal(self):
        fields = (self.timestamp,
                  self.period,
                  self.count,
                  self.period_count,
                  self.latency,
                  self.cpu_time,
                  self.period_cpu_time,
                  self.rss)

        fields = map(str, fields)
        line = "{}\n".format(",".join(fields))

        return line.encode("ascii")

    def unmarshal(self, line):
        line = line.decode("ascii")
        fields = [int(x) for x in line.split(",")]

        (self.timestamp,
         self.period,
         self.count,
         self.period_count,
         self.latency,
         self.cpu_time,
         self.period_cpu_time,
         self.rss) = fields

_join = _plano.join
_ticks_per_ms = _os.sysconf(_os.sysconf_names["SC_CLK_TCK"]) / 1000
_page_size = _resource.getpagesize()
