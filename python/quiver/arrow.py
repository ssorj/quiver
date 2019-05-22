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
import traceback

from .common import *
from .common import __version__
from .common import _epilog_address_urls
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

{_epilog_address_urls}

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
        self.parser.add_argument("url", metavar="ADDRESS-URL",
                                 help="The location of a message source or target")
        self.parser.add_argument("--output", metavar="DIR",
                                 help="Save output files to DIR")
        self.parser.add_argument("--impl", metavar="NAME",
                                 help="Use NAME implementation",
                                 default=DEFAULT_ARROW_IMPL)
        self.parser.add_argument("--info", action="store_true",
                                 help="Print implementation details and exit")
        self.parser.add_argument("--impl-info", action="store_true", dest="info",
                                 help=_argparse.SUPPRESS)
        self.parser.add_argument("--id", metavar="ID",
                                 help="Use ID as the client or server identity")
        self.parser.add_argument("--server", action="store_true",
                                 help="Operate in server mode")
        self.parser.add_argument("--passive", action="store_true",
                                 help="Operate in passive mode")
        self.parser.add_argument("--prelude", metavar="PRELUDE", default="",
                                 help="Commands to precede the implementation invocation")
        self.parser.add_argument("--cert", metavar="CERT.PEM",
                                 help="Certificate filename - used for client authentication")
        self.parser.add_argument("--key", metavar="PRIVATE-KEY.PEM",
                                 help="Private key filename - used for client authentication")

        self.add_common_test_arguments()
        self.add_common_tool_arguments()

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
            self.transfers_parse_func = _parse_send
        elif self.operation == "receive":
            self.role = "receiver"
            self.transfers_parse_func = _parse_receive
        else:
            raise Exception()
        self.is_receiver = self.role == "receiver"

        if self.id_ is None:
            self.id_ = "quiver-{}-{}".format(self.role, _plano.unique_id(4))

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
            if self.impl.name in ("activemq-jms", "activemq-artemis-jms"):
                self.port = "61616"

        # XXX Drop the flags stuff

        flags = list()

        if self.durable:
            flags.append("durable")

        self.flags = ",".join(flags)

        self.snapshots_file = _join(self.output_dir, "{}-snapshots.csv".format(self.role))
        self.summary_file = _join(self.output_dir, "{}-summary.json".format(self.role))
        self.transfers_file = _join(self.output_dir, "{}-transfers.csv".format(self.role))
        self.settlement_file = _join(self.output_dir, "{}-settlement.csv".format(self.role))

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
        self.latency_average_settlement = None
        self.latency_quartiles_settlement = None
        self.latency_nines_settlement = None
        self.summary_transfers = None
        self.summary_settlements = None

        self.no_credit_events = 0
        self.no_credit_duration = 0
        self.no_credit_start = 0

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
            "body-size={}".format(self.body_size),
            "credit-window={}".format(self.credit_window),
            "transaction-size={}".format(self.transaction_size),
            "durable={}".format(1 if self.durable else 0),
            "settlement={}".format(1 if self.settlement else 0)
        ]

        if self.username:
            args.append("username={}".format(self.username))

        if self.password:
            args.append("password={}".format(self.password))

        if self.args.cert and self.args.key:
            args.append("key={}".format(self.key))
            args.append("cert={}".format(self.cert))

        with open(self.transfers_file, "wb") as fout:
            env = _plano.ENV

            if self.verbose:
                env["QUIVER_VERBOSE"] = "1"

            proc = _plano.start_process(args, stdout=fout, env=env)

            try:
                self.monitor_subprocess(proc)
            except:
                _plano.stop_process(proc)
                raise

            if proc.returncode != 0:
                raise CommandError("{} exited with code {}", self.role, proc.returncode)

        if _plano.file_size(self.transfers_file) == 0:
            raise CommandError("No transfers")

        self.compute_results()
        self.save_summary()

        if _plano.exists("{}.xz".format(self.transfers_file)):
            _plano.remove("{}.xz".format(self.transfers_file))

        _plano.call("xz --compress -0 --keep --threads 0 {}", self.transfers_file)

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

        #print("check_timeout", snap.count, "==", checkpoint.count, "and", since, ">", self.timeout)

        if snap.count == checkpoint.count and since > self.timeout:
            raise CommandError("{} timed out", self.role)

        if snap.count > checkpoint.count:
            self.timeout_checkpoint = snap

    def is_settlement_record(self, line):
        # Settlement lines start with 'S' or 's'
        return line[0] == ord(PREFIX_SETTLEMENT_BULK) or line[0] == ord(PREFIX_SETTLEMENT_RUNTIME)

    def is_runtime_settlement_record(self, line):
        # Runtime settlement lines start with 'S'
        return line[0] == ord(PREFIX_SETTLEMENT_RUNTIME)

    def is_settle_tag_candidate(self, id):
        # Settlement latency calculated on first message and every 256 messages thereafter
        return (int(id) & 255) == 1

    def compute_results(self):
        self.summary_transfers = list()
        self.summary_settlements = list()
        unsettleds = dict()
        with open(self.transfers_file, "rb") as f:
            for line in f:
                try:
                    if not self.settlement or self.is_receiver:
                        transfer = self.transfers_parse_func(line)
                        self.summary_transfers.append(transfer)
                    else:
                        if self.is_settlement_record(line):
                            settle_tag, settle_time, dummy = self.transfers_parse_func(line[1:])
                            if settle_tag in unsettleds:
                                settlement = settle_tag, unsettleds[settle_tag], settle_time
                                self.summary_settlements.append(settlement)
                                del unsettleds[settle_tag]
                            else:
                                _plano.error("Failed to match results message with settlement id '{}'",
                                                settle_tag)
                        else:
                            transfer = self.transfers_parse_func(line)
                            self.summary_transfers.append(transfer)
                            id, s_time, credit = transfer
                            unsettleds[id] = s_time
                            if self.no_credit_start == 0:
                                if credit == 1:
                                    self.no_credit_start = s_time
                                else:
                                    pass # this transfer did not consume the last of the credit
                            else:
                                self.no_credit_events += 1
                                self.no_credit_duration += s_time - self.no_credit_start
                                self.no_credit_start = 0
                except Exception as e:
                    _plano.error("Failed to process results line '{}': {}", line, e)
                    continue

        self.message_count = len(self.summary_transfers)

        if self.message_count == 0:
            return

        if self.operation == "send":
            self.first_send_time = self.summary_transfers[0][1]
            self.last_send_time = self.summary_transfers[-1][1]

            duration = (self.last_send_time - self.first_send_time) / 1000000

            if self.settlement and (len(self.summary_settlements) > 0):
                self.compute_latencies(self.summary_settlements, True)

        elif self.operation == "receive":
            self.first_receive_time = self.summary_transfers[0][2]
            self.last_receive_time = self.summary_transfers[-1][2]

            duration = (self.last_receive_time - self.first_receive_time) / 1000000

            self.compute_latencies(self.summary_transfers)
        else:
            raise Exception()

        if duration > 0:
            self.message_rate = int(round(self.message_count / duration))

    def compute_latencies(self, transfers, settlement_latencies=False):
        latencies = list()

        for id_, send_time, receive_time in transfers:
            latency = receive_time - send_time
            latencies.append(latency)

        latencies = _numpy.array(latencies, _numpy.int32)

        q = 0, 25, 50, 75, 100, 90, 99, 99.9, 99.99, 99.999
        percentiles = _numpy.percentile(latencies, q)
        percentiles = [int(x) for x in percentiles]

        if settlement_latencies:
            self.latency_average_settlement = _numpy.mean(latencies)
            self.latency_quartiles_settlement = percentiles[:5]
            self.latency_nines_settlement = percentiles[5:]
        else:
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
                "body_size": self.body_size,
                "credit_window": self.credit_window,
                "transaction_size": self.transaction_size,
                "durable": self.durable,
                "settlement": self.settlement,
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
                "latency_average_settlement": self.latency_average_settlement,
                "latency_quartiles_settlement": self.latency_quartiles_settlement,
                "latency_nines_settlement": self.latency_nines_settlement,
                "no_credit_events": self.no_credit_events,
                "no_credit_duration": self.no_credit_duration,
            },
        }

        with open(self.summary_file, "w") as f:
            _json.dump(props, f, indent=2)

        if self.settlement and len(self.summary_settlements) > 0:
            with open(self.settlement_file, "w") as f:
                f.write("id, settle_latency\n")
                for i in range(len(self.summary_settlements)):
                    s = self.summary_settlements[i]
                    f.write("%d, %d\n" % (int(s[0]), (int(s[2]) - int(s[1]))))

        if self.is_receiver:
            with open(self.settlement_file, "w") as f:
                f.write("id, send_latency\n")
                for i in range(len(self.summary_transfers)):
                    s = self.summary_transfers[i]
                    f.write("%d, %d\n" % (int(s[0]), (int(s[2]) - int(s[1]))))

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

        self.unsettleds = dict() if previous is None else previous.unsettleds

    def capture(self, transfers_file, proc):
        self.timestamp = now()
        self.period = self.timestamp - self.command.start_time

        if self.previous is not None:
            self.period = self.timestamp - self.previous.timestamp

        self.capture_transfers(transfers_file)
        self.capture_proc_info(proc)

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

    def capture_transfers(self, transfers_file):
        transfers = list()
        settlements = list()
        do_settlement = self.command.settlement and not self.command.is_receiver

        for line in _read_lines(transfers_file):
            try:
                if do_settlement:
                    if self.command.is_settlement_record(line):
                        if self.command.is_runtime_settlement_record(line):
                            settle_tag, settle_time, dummy = self.command.transfers_parse_func(line[1:])
                            if settle_tag in self.unsettleds:
                                record = settle_tag, self.unsettleds[settle_tag], settle_time
                                settlements.append(record)
                                del self.unsettleds[settle_tag]
                            else:
                                _plano.error("Failed to match capture message with settlement id '{}'",
                                                settle_tag)
                        else:
                            # ignore bulk of settlement records
                            pass
                    else:
                        record = self.command.transfers_parse_func(line)
                        transfers.append(record)
                        if self.command.is_settle_tag_candidate(record[0]):
                            self.unsettleds[record[0]] = record[1]
                else:
                    record = self.command.transfers_parse_func(line)
                    transfers.append(record)

            except Exception as e:
                _plano.error("Failed to process capture line '{}': {}", line, e)
                continue

        self.period_count = len(transfers)
        self.count = self.previous.count + self.period_count

        if self.period_count > 0:
            latencies = list()
            if self.command.is_receiver:
                for id_, send_time, receive_time in transfers:
                    latency = receive_time - send_time
                    latencies.append(latency)

                self.latency = int(_numpy.mean(latencies))
            else:
                if do_settlement:
                    for id_, send_time, receive_time in settlements:
                        latency = receive_time - send_time
                        latencies.append(latency)

                    self.latency = int(_numpy.mean(latencies))
                else:
                    self.latency = 0

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

def _read_lines(file_):
    while True:
        fpos = file_.tell()
        line = file_.readline()

        if line == b"":
            break

        if not line.endswith(b"\n"):
            file_.seek(fpos)
            break

        yield line[:-1]

def _parse_send(line):
    message_id, send_time, credit = line.split(b",", 2)
    send_time = int(send_time)
    credit = int(credit)

    return message_id, send_time, credit

def _parse_receive(line):
    message_id, send_time, receive_time = line.split(b",", 2)
    send_time = int(send_time)
    receive_time = int(receive_time)

    return message_id, send_time, receive_time

_join = _plano.join
_ticks_per_ms = _os.sysconf(_os.sysconf_names["SC_CLK_TCK"]) / 1000
_page_size = _resource.getpagesize()
