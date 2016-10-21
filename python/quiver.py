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
import binascii as _binascii
import json as _json
import numpy as _numpy
import os as _os
import resource as _resource
import signal as _signal
import string as _string
import subprocess as _subprocess
import sys as _sys
import tempfile as _tempfile
import time as _time
import uuid as _uuid

_impls_by_name = {
    "activemq-jms": "activemq-jms",
    "activemq-artemis-jms": "activemq-artemis-jms",
    "artemis-jms": "activemq-artemis-jms",
    "cpp": "qpid-proton-cpp",
    "java": "vertx-proton",
    "javascript": "rhea",
    "jms": "qpid-jms",
    "python": "qpid-proton-python",
    "qpid-jms": "qpid-jms",
    "qpid-messaging-cpp": "qpid-messaging-cpp",
    "qpid-messaging-python": "qpid-messaging-python",
    "qpid-proton-cpp": "qpid-proton-cpp",
    "qpid-proton-python": "qpid-proton-python",
    "rhea": "rhea",
    "vertx-proton": "vertx-proton",
}

_common_epilog = """
addresses:
  [//DOMAIN/]PATH                 The default domain is 'localhost'
  //example.net/jobs
  //10.0.0.10:5672/jobs/alpha
  //localhost/q0
  q0

implementations:
  activemq-artemis-jms            Client mode only; requires Artemis server
  activemq-jms                    Client mode only; ActiveMQ or Artemis server
  qpid-jms [jms]                  Client mode only
  qpid-messaging-cpp              Client mode only
  qpid-messaging-python           Client mode only
  qpid-proton-cpp [cpp]
  qpid-proton-python [python]
  rhea [javascript]
  vertx-proton [java]             Client mode only
"""

_quiver_description = """
Start a sender-receiver pair for a particular messaging address.

'quiver' is one of the Quiver tools for testing the performance of
message servers and APIs.
"""

_quiver_epilog = """
{}
example usage:
  $ qdrouterd &                   # Start a message server
  $ quiver q0                     # Start test
"""

_quiver_arrow_description = """
Send or receive a set number of messages as fast as possible using a
single connection.

'quiver-arrow' is one of the Quiver tools for testing the performance
of message servers and APIs.
"""

# XXX Document server and passive mode
# By default arrow operates in client, active mode ...

_quiver_arrow_epilog = """
operations:
  send                  Send messages
  receive               Receive messages

{}
example usage:
  $ qdrouterd &                   # Start a message server
  $ quiver-arrow receive q0 &     # Start receiving
  $ quiver-arrow send q0          # Start sending
"""

_common_epilog = _common_epilog.lstrip()

_quiver_description = _quiver_description.lstrip()
_quiver_epilog = _quiver_epilog.lstrip()
_quiver_epilog = _quiver_epilog.format(_common_epilog)

_quiver_arrow_description = _quiver_arrow_description.lstrip()
_quiver_arrow_epilog = _quiver_arrow_epilog.lstrip()
_quiver_arrow_epilog = _quiver_arrow_epilog.format(_common_epilog)

class QuiverError(Exception):
    pass

class _Command(object):
    def __init__(self, home_dir):
        self.home_dir = home_dir

        self.parser = None
        self.args = None

        self.verbose = False
        self.quiet = False

    def init(self):
        assert self.parser is not None

        self.add_common_arguments()

        self.args = self.parser.parse_args()

        try:
            self.impl = _impls_by_name[self.args.impl]
        except KeyError:
            m = "Implementation '{}' is unknown".format(self.args.impl)
            self.parser.error(m)

        self.address = self.args.address
        self.messages = self.parse_int_with_unit(self.args.messages)
        self.body_size = self.parse_int_with_unit(self.args.body_size)
        self.credit_window = self.parse_int_with_unit(self.args.credit)
        self.timeout = self.parse_int_with_unit(self.args.timeout)

        self.output_dir = self.args.output
        self.init_only = self.args.init_only
        self.quiet = self.args.quiet
        self.verbose = self.args.verbose

        if self.output_dir is None:
            self.output_dir = _tempfile.mkdtemp(prefix="quiver-")

        if not _os.path.exists(self.output_dir):
            _os.makedirs(self.output_dir)

    def add_common_arguments(self):
        self.parser.add_argument("address", metavar="ADDRESS",
                                 help="The location of a message queue")
        self.parser.add_argument("-m", "--messages", metavar="COUNT",
                                 help="Send or receive COUNT messages",
                                 default="1m")
        self.parser.add_argument("--impl", metavar="NAME",
                                 help="Use NAME implementation",
                                 default="qpid-proton-python")
        self.parser.add_argument("--body-size", metavar="COUNT",
                                 help="Send message bodies containing COUNT bytes",
                                 default="100")
        self.parser.add_argument("--credit", metavar="COUNT",
                                 help="Sustain credit for COUNT incoming transfers",
                                 default="1k")
        self.parser.add_argument("--timeout", metavar="SECONDS",
                                 help="Fail after SECONDS without transfers",
                                 default="10")
        self.parser.add_argument("--output", metavar="DIRECTORY",
                                 help="Save output files to DIRECTORY")
        self.parser.add_argument("--init-only", action="store_true",
                                 help="Initialize and immediately exit")
        self.parser.add_argument("--quiet", action="store_true",
                                 help="Print nothing to the console")
        self.parser.add_argument("--verbose", action="store_true",
                                 help="Print details to the console")

    def parse_int_with_unit(self, value):
        assert self.parser is not None

        try:
            if value.endswith("m"): return int(value[:-1]) * 1000 * 1000
            if value.endswith("k"): return int(value[:-1]) * 1000
            return int(value)
        except ValueError:
            m = "Failure parsing '{}' as integer with unit".format(value)
            self.parser.error(m)

    def vprint(self, message, *args, **kwargs):
        if not self.verbose:
            return

        message = "{}: {}".format(_program, message)
        print(message.format(*args), **kwargs)

class QuiverCommand(_Command):
    def __init__(self, home_dir):
        super(QuiverCommand, self).__init__(home_dir)

        self.parser = _argparse.ArgumentParser(description=_quiver_description,
                                               epilog=_quiver_epilog,
                                               formatter_class=_Formatter)
        self.start_time = None
        self.end_time = None

    def run(self):
        args = _sys.argv[2:]

        if "--output" not in args:
            args += "--output", self.output_dir

        sender_args = ["quiver-arrow", "send", self.address] + args
        receiver_args = ["quiver-arrow", "receive", self.address] + args

        self.start_time = now()

        receiver = _subprocess.Popen(receiver_args)
        sender = _subprocess.Popen(sender_args)

        if not self.quiet:
            self.print_status(sender, receiver)

        sender.wait()
        receiver.wait()

        self.end_time = now()

        if not self.quiet:
            self.print_summary()

    def print_status(self, sender, receiver):
        sender_snaps = _join(self.output_dir, "sender-snapshots.csv")
        receiver_snaps = _join(self.output_dir, "receiver-snapshots.csv")

        _touch(sender_snaps)
        _touch(receiver_snaps)

        ssnap, rsnap = None, None
        i = 0

        with open(sender_snaps, "rb") as fs, open(receiver_snaps, "rb") as fr:
            while receiver.poll() == None:
                _time.sleep(1)

                sline = _read_whole_line(fs)
                rline = _read_whole_line(fr)

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
        ("T [s]", "Count [m]", "Rate [m/s]", "CPU [%]", "RSS [M]",
         "T [s]", "Count [m]", "Rate [m/s]", "CPU [%]", "RSS [M]",
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

        v = ", ".join((self.output_dir, self.impl, self.address))
        print("Subject: {}".format(v))

        _print_numeric_field("Messages", self.messages, "messages")
        _print_numeric_field("Body size", self.body_size, "bytes")
        _print_numeric_field("Credit window", self.credit_window, "messages")

        duration = (self.end_time - self.start_time) / 1000

        _print_numeric_field("Duration", duration, "s", "{:,.1f}")

        # XXX Sender and receiver CPU, RSS

        v = sender["results"]["message_rate"]
        _print_numeric_field("Sender rate", v, "messages/s")
        v = receiver["results"]["message_rate"]
        _print_numeric_field("Receiver rate", v, "messages/s")
        v = receiver["results"]["message_count"] / duration
        _print_numeric_field("End-to-end rate", v, "messages/s")
        v = receiver["results"]["latency_average"]
        _print_numeric_field("Average latency", v, "ms", "{:,.1f}")
        v = receiver["results"]["latency_quartiles"]
        v = ", ".join(map(str, v))
        _print_numeric_field("Latency 25, 50, 75, 100%", v, "ms", None)
        v = receiver["results"]["latency_nines"][:3]
        v = ", ".join(map(str, v))
        _print_numeric_field("Latency 99, 99.9, 99.99%", v, "ms", None)

        print("-" * 80)

class QuiverArrowCommand(_Command):
    def __init__(self, home_dir):
        super(QuiverArrowCommand, self).__init__(home_dir)

        self.start_time = None
        self.end_time = None
        self.timeout_checkpoint = None

        self.parser = _argparse.ArgumentParser(description=_quiver_arrow_description,
                                               epilog=_quiver_arrow_epilog,
                                               formatter_class=_Formatter)

        self.parser.add_argument("operation", metavar="OPERATION",
                                 choices=["send", "receive"],
                                 help="Either 'send' or 'receive'")
        self.parser.add_argument("--id", metavar="ID",
                                 help="Use ID as the client or server identity")
        self.parser.add_argument("--server", action="store_true",
                                 help="Operate in server mode")
        self.parser.add_argument("--passive", action="store_true",
                                 help="Operate in passive mode")

    def init(self):
        super(QuiverArrowCommand, self).init()

        self.connection_mode = "client"
        self.channel_mode = "active"
        self.operation = self.args.operation
        self.id_ = self.args.id

        if self.args.server:
            self.connection_mode = "server"
            self.channel_mode = "passive"

        if self.args.passive:
            self.channel_mode = "passive"

        if self.id_ is None:
            self.id_ = "quiver-{}".format(_unique_id(4))

        if self.address.startswith("//"):
            domain, self.path = self.address[2:].split("/", 1)
        else:
            domain, self.path = "localhost", self.address

        if ":" in domain:
            self.host, self.port = domain.split(":", 1)
        else:
            self.host, self.port = domain, "-"

        self.impl_file = "{}/exec/arrow-{}".format(self.home_dir, self.impl)

        if not _os.path.exists(self.impl_file):
            m = "No impl at '{}'".format(self.impl_file)
            raise QuiverError(m)

        if self.operation == "send":
            self.snapshots_file = _join(self.output_dir, "sender-snapshots.csv")
            self.summary_file = _join(self.output_dir, "sender-summary.json")
            self.transfers_file = _join(self.output_dir, "sender-transfers.csv")
            self.transfers_parse_func = _parse_send
        elif self.operation == "receive":
            self.snapshots_file = _join(self.output_dir, "receiver-snapshots.csv")
            self.summary_file = _join(self.output_dir, "receiver-summary.json")
            self.transfers_file = _join(self.output_dir, "receiver-transfers.csv")
            self.transfers_parse_func = _parse_receive
        else:
            raise Exception()

        self.message_count = None
        self.message_rate = None
        self.latency_average = None
        self.latency_quartiles = None
        self.latency_nines = None

    def run(self):
        args = (
            self.impl_file,
            self.connection_mode,
            self.channel_mode,
            self.operation,
            self.id_,
            self.host,
            self.port,
            self.path,
            str(self.messages),
            str(self.body_size),
            str(self.credit_window),
        )

        assert None not in args, args

        self.vprint("Calling '{}'", " ".join(args))

        with open(self.transfers_file, "wb") as fout:
            proc = _subprocess.Popen(args, stdout=fout)

            self.start_time = now()
            self.vprint("Process {} ({}) started", proc.pid, self.operation)

            snap = _StatusSnapshot(self, None)
            snap.timestamp = now() # XXX Versus start_time

            self.timeout_checkpoint = snap

            sleep = 2.0

            with open(self.transfers_file, "rb") as fin:
                with open(self.snapshots_file, "ab") as fout:
                    while proc.poll() is None:
                        _time.sleep(sleep)

                        period_start = _time.time()

                        snap.previous = None
                        snap = _StatusSnapshot(self, snap)

                        snap.capture(fin, proc)

                        fout.write(snap.marshal())
                        fout.flush()

                        self.check_timeout(snap, proc)

                        period = _time.time() - period_start
                        sleep = max(1.0, 2.0 - period)

            self.end_time = now()

            if proc.returncode == 0:
                m = "Process {} ({}) exited normally"
                self.vprint(m, proc.pid, self.operation)
            else:
                m = "Process {} ({}) exited with code {}"
                m = m.format(proc.pid, self.operation, proc.returncode)
                raise QuiverError(m)

        if _os.path.getsize(self.transfers_file) == 0:
            raise QuiverError("No transfers")

        self.compute_results()
        self.save_summary()

        _compress_file(self.transfers_file)

    def check_timeout(self, snap, proc):
        checkpoint = self.timeout_checkpoint
        since = (snap.timestamp - checkpoint.timestamp) / 1000

        if snap.count == checkpoint.count and since > self.timeout:
            m = "{} operation timed out"
            eprint(m, _string.capitalize(self.operation))

            _os.killpg(_os.getpgid(proc.pid), _signal.SIGTERM)

        if snap.count > checkpoint.count:
            self.timeout_checkpoint = snap

    def compute_results(self):
        duration = (self.end_time - self.start_time) / 1000
        transfers = list()

        with open(self.transfers_file, "rb") as f:
            for line in f:
                try:
                    transfer = self.transfers_parse_func(line)
                except Exception as e:
                    eprint("Failed to parse line '{}': {}", line, str(e))
                    continue

                transfers.append(transfer)

        self.message_count = len(transfers)
        self.message_rate = int(round(self.message_count / duration))

        if self.operation == "receive":
            latencies = list()

            for id_, send_time, receive_time in transfers:
                latency = receive_time - send_time
                latencies.append(latency)

            latencies = _numpy.array(latencies, _numpy.int32)

            q = 25, 50, 75, 100, 99, 99.9, 99.99, 99.999
            percentiles = _numpy.percentile(latencies, q, interpolation="higher")
            percentiles = map(int, percentiles)

            self.latency_average = _numpy.mean(latencies)
            self.latency_quartiles = percentiles[:4]
            self.latency_nines = percentiles[4:]

    def save_summary(self):
        props = {
            "config": {
                "impl": self.impl,
                "address": self.address,
                "output_dir": self.output_dir,
                "connection_mode": self.connection_mode,
                "channel_mode": self.channel_mode,
                "operation": self.operation,
                "id": self.id_,
                "messages": self.messages,
                "body_size": self.body_size,
                "credit_window": self.credit_window,
                "timeout": self.timeout,
            },
            "results": {
                "message_count": self.message_count,
                "message_rate": self.message_rate,
                "latency_average": self.latency_average,
                "latency_quartiles": self.latency_quartiles,
                "latency_nines": self.latency_nines,
            },
        }

        with open(self.summary_file, "wb") as f:
            _json.dump(props, f, indent=2)

class _Formatter(_argparse.ArgumentDefaultsHelpFormatter,
                 _argparse.RawDescriptionHelpFormatter):
    pass

class _StatusSnapshot(object):
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

        while True:
            lines = _read_lines(transfers_file)

            if lines is None:
                break

            for line in lines:
                try:
                    record = self.command.transfers_parse_func(line)
                except Exception as e:
                    eprint("Failed to parse line '{}': {}", line, str(e))
                    continue

                transfers.append(record)

        self.period_count = len(transfers)
        self.count = self.previous.count + self.period_count

        if self.period_count > 0 and self.command.operation == "receive":
            latencies = list()

            for id_, send_time, receive_time in transfers:
                latency = receive_time - send_time
                latencies.append(latency)

            self.latency = int(_numpy.mean(latencies))

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
        line = b"{}\n".format(b",".join(fields))

        return line

    def unmarshal(self, line):
        fields = map(int, line.split(b","))

        (self.timestamp,
         self.period,
         self.count,
         self.period_count,
         self.latency,
         self.cpu_time,
         self.period_cpu_time,
         self.rss) = fields

def eprint(message, *args, **kwargs):
    if isinstance(message, Exception):
        message = str(message)

    message = "{}: {}".format(_program, message)
    message = message.format(*args)

    print(message, file=_sys.stderr, **kwargs)

def now():
    return long(_time.time() * 1000)

def _parse_send(line):
    message_id, send_time = line.split(b",", 1)
    send_time = int(send_time)

    return message_id, send_time

def _parse_receive(line):
    message_id, send_time, receive_time = line.split(b",", 2)
    send_time = int(send_time)
    receive_time = int(receive_time)

    return message_id, send_time, receive_time

def _print_numeric_field(name, value, unit, fmt="{:,.0f}"):
    name = "{}:".format(name)

    if fmt is not None:
        value = fmt.format(value)

    print("{:<28} {:>28} {}".format(name, value, unit))

def _unique_id(length=16):
    assert length >= 1
    assert length <= 16

    uuid_bytes = _uuid.uuid4().bytes
    uuid_bytes = uuid_bytes[:length]

    return _binascii.hexlify(uuid_bytes).decode("utf-8")

def _touch(path):
    with open(path, "ab") as f:
        f.write(b"")

def _read_whole_line(file_):
    fpos = file_.tell()
    line = file_.readline()

    if line == "" or line[-1] != b"\n":
        file_.seek(fpos)
        return

    return line[:-1]

def _read_lines(file_):
    data = file_.read(8192)

    if data == "":
        return

    lines = data.split(b"\n")
    last_line = lines[-1]

    if last_line != "":
        file_.seek(file_.tell() - len(last_line))

    return lines[:-1]

def _compress_file(path):
    args = "xz", "--compress", "-0", "--threads", "0", path
    _subprocess.check_call(args)

_join = _os.path.join

_program = _os.path.split(_sys.argv[0])[1]
_ticks_per_ms = _os.sysconf(_os.sysconf_names["SC_CLK_TCK"]) / 1000
_page_size = _resource.getpagesize()
