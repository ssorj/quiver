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
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import with_statement

import argparse as _argparse
import binascii as _binascii
import numpy as _numpy
import os as _os
import resource as _resource
import signal as _signal
import string as _string
import subprocess as _subprocess
import sys as _sys
import tempfile as _tempfile
import threading as _threading
import time as _time
import traceback as _traceback
import uuid as _uuid

_impls_by_name = {
    "activemq-jms": "activemq-jms",
    "activemq-artemis-jms": "activemq-artemis-jms",
    "artemis-jms": "activemq-artemis-jms",
    "javascript": "rhea",
    "jms": "qpid-jms",
    "python": "qpid-proton-python",
    "qpid-jms": "qpid-jms",
    "qpid-messaging-cpp": "qpid-messaging-cpp",
    "qpid-messaging-python": "qpid-messaging-python",
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
  qpid-proton-python [python]
  rhea [javascript]               Client mode only at the moment
  vertx-proton                    Client mode only
"""

_quiver_description = """
Start message senders and receivers for a particular messaging
address.

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
server and 

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

def _add_common_arguments(parser):
    parser.add_argument("address", metavar="ADDRESS",
                        help="The location of a message queue")
    parser.add_argument("-m", "--messages", metavar="COUNT",
                        help="Send or receive COUNT messages",
                        default="1m")
    parser.add_argument("--impl", metavar="NAME",
                        help="Use NAME implementation",
                        default="qpid-proton-python")
    parser.add_argument("--bytes", metavar="COUNT",
                        help="Send message bodies containing COUNT bytes",
                        default="100")
    parser.add_argument("--credit", metavar="COUNT",
                        help="Sustain credit for COUNT incoming transfers",
                        default="1k")
    parser.add_argument("--timeout", metavar="SECONDS",
                        help="Fail after SECONDS without transfers",
                        default=10, type=int)
    parser.add_argument("--output", metavar="DIRECTORY",
                        help="Save output files to DIRECTORY")
    parser.add_argument("--init-only", action="store_true",
                        help="Initialize and immediately exit")
    parser.add_argument("--quiet", action="store_true",
                        help="Print nothing to the console")
    parser.add_argument("--verbose", action="store_true",
                        help="Print details to the console")

class QuiverError(Exception):
    pass

class QuiverCommand(object):
    def __init__(self, home_dir):
        self.home_dir = home_dir

        self.parser = _argparse.ArgumentParser \
            (description=_quiver_description,
             epilog=_quiver_epilog,
             formatter_class=_Formatter)

        _add_common_arguments(self.parser)
        
    def init(self):
        args = self.parser.parse_args()

        self.address = args.address
        self.init_only = args.init_only

    def run(self):
        sender_count = 1 # max(args.pairs, args.senders)
        receiver_count = 1 # max(args.pairs, args.receivers)

        args = _sys.argv[2:]

        if "--output" not in args:
            args += "--output", _tempfile.mkdtemp(prefix="quiver-")
        
        sender_args = ["quiver-arrow", "send", self.address]
        sender_args += args

        receiver_args = ["quiver-arrow", "receive", self.address]
        receiver_args += args

        senders = list()
        receivers = list()
        
        for i in range(receiver_count):
            receiver = _subprocess.Popen(receiver_args)
            receivers.append(receiver)

        _time.sleep(0.1)

        for i in range(sender_count):
            sender = _subprocess.Popen(sender_args)
            senders.append(sender)

        for sender in senders:
            sender.wait()

        for receiver in receivers:
            receiver.wait()
        
class QuiverArrowCommand(object):
    def __init__(self, home_dir):
        self.home_dir = home_dir

        self.start_time = None
        self.end_time = None

        self.started = _threading.Event()
        self.stop = _threading.Event()
        self.ended = _threading.Event()

        self.proc = None
        
        self.parser = _argparse.ArgumentParser \
            (description=_quiver_arrow_description,
             epilog=_quiver_arrow_epilog,
             formatter_class=_Formatter)

        self.parser.add_argument("operation", metavar="OPERATION",
                                 choices=["send", "receive"],
                                 help="Either 'send' or 'receive'")
        
        _add_common_arguments(self.parser)
        
        self.parser.add_argument("--id", metavar="ID",
                                 help="Use ID as the client or server identity")
        self.parser.add_argument("--server", action="store_true",
                                 help="Operate in server mode")
        self.parser.add_argument("--passive", action="store_true",
                                 help="Operate in passive mode")
    
        self.periodic_status_thread = _PeriodicStatusThread(self)

    def init(self):
        args = self.parser.parse_args()

        messages = _parse_int_with_unit(self.parser, args.messages)
        bytes_ = _parse_int_with_unit(self.parser, args.bytes)
        credit = _parse_int_with_unit(self.parser, args.credit)
        
        try:
            self.impl = _impls_by_name[args.impl]
        except KeyError:
            self.parser.error("Implementation '{}' is unknown".format(args.impl))

        self.connection_mode = "client"
        self.channel_mode = "active"
        self.operation = args.operation
        self.id_ = args.id
        self.address = args.address
        self.messages = messages
        self.bytes_ = bytes_
        self.credit = credit

        self.output_dir = args.output
        self.init_only = args.init_only
        self.timeout = args.timeout
        self.quiet = args.quiet
        self.verbose = args.verbose
        
        if args.server:
            self.connection_mode = "server"
            self.channel_mode = "passive"

        if args.passive:
            self.channel_mode = "passive"
        
        if self.output_dir is None:
            self.output_dir = _tempfile.mkdtemp(prefix="quiver-")
            
        if not _os.path.exists(self.output_dir):
            _os.makedirs(self.output_dir)

        impl_name = "arrow-{}".format(self.impl)
        self.impl_file = _os.path.join(self.home_dir, "exec", impl_name)

        if self.operation == "send":
            self.output_file = _os.path.join(self.output_dir, "sender.csv")
        elif self.operation == "receive":
            self.output_file = _os.path.join(self.output_dir, "receiver.csv")
        else:
            raise Exception()
        
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

        if not _os.path.exists(self.impl_file):
            msg = "No impl at '{}'".format(self.impl_file)
            raise QuiverError(msg)
        
        if not _os.path.isdir(self.output_dir):
            msg = "Invalid output dir at '{}'".format(self.output_dir)
            raise QuiverError(msg)

        self.periodic_status_thread.init()
            
    def run(self):
        self.periodic_status_thread.start()

        args = [
            self.impl_file,
            self.connection_mode,
            self.channel_mode,
            self.operation,
            self.id_,
            self.host,
            self.port,
            self.path,
            str(self.messages),
            str(self.bytes_),
            str(self.credit),
        ]

        assert None not in args, args
        
        self.vprint("Calling '{}'", " ".join(args))

        if self.verbose:
            self.print_config()

        with open(self.output_file, "w") as fout:
            self.proc = _subprocess.Popen(args, stdout=fout)

            self.vprint("Process {} ({}) started", self.proc.pid,
                        self.operation)

            self.started.set()
            self.start_time = _time.time()

            while self.proc.poll() == None:
                if self.stop.wait(0.1):
                    _os.killpg(_os.getpgid(self.proc.pid), _signal.SIGTERM)

            self.end_time = _time.time()
            self.ended.set()

            if self.proc.returncode == 0:
                self.vprint("Process {} ({}) exited normally", self.proc.pid,
                            self.operation)
            else:
                msg = "Process {} ({}) exited with code {}".format \
                      (self.proc.pid, self.operation, self.proc.returncode)
                raise QuiverError(msg)
                    
        if self.operation == "receive":
            if _os.path.getsize(self.output_file) == 0:
                raise QuiverError("No transfers")
        
            if not self.quiet:
                self.print_results()

        self.compress_output()

    def vprint(self, msg, *args):
        if not self.verbose:
            return
        
        msg = "quiver: {}".format(msg)
        print(msg.format(*args))

    def print_config(self):
        _print_bracket()
        _print_field("Output", self.output_file)
        _print_field("Implementation", self.impl)
        _print_field("Connection mode", self.connection_mode)
        _print_field("Channel mode", self.channel_mode)
        _print_field("Operation", self.operation)
        _print_field("ID", self.id_)
        _print_field("Address", self.address)
        _print_field("Messages", "{:,d}".format(self.messages))
        _print_field("Bytes", "{:,d}".format(self.bytes_))
        _print_field("Credit", "{:,d}".format(self.credit))
        _print_bracket()
            
    def print_results(self):
        latencies = list()

        with open(self.output_file, "r") as f:
            for line in f:
                message_id, send_time, receive_time = line.split(",", 2)

                send_time = long(send_time)
                receive_time = long(receive_time)
                latency = receive_time - send_time

                latencies.append(latency)

        duration = self.end_time - self.start_time
        transfers = len(latencies)
        rate = int(round(transfers / duration))
        latency = _numpy.mean(latencies)

        quartiles = (_numpy.percentile(latencies, 25),
                     _numpy.percentile(latencies, 50),
                     _numpy.percentile(latencies, 75),
                     _numpy.percentile(latencies, 100))
        fquartiles = "{:,.0f} | {:,.0f} | {:,.0f} | {:,.0f}".format(*quartiles)
        
        _print_bracket()
        _print_numeric_field("Duration", duration, "s", "{:,.1f}")
        _print_numeric_field("Message count", transfers, "messages", "{:,d}")
        _print_numeric_field("Message rate", rate, "messages/s", "{:,d}")
        _print_numeric_field("Latency average", latency, "ms", "{:,.1f}")
        _print_numeric_field("Latency by quartile", fquartiles, "ms")
        _print_bracket()

    def compress_output(self):
        args = "xz", "--compress", "-0", "--threads", "0", self.output_file
        _subprocess.check_call(args)

def _parse_int_with_unit(parser, value):
    try:
        if value.endswith("m"): return int(value[:-1]) * 1000 * 1000
        if value.endswith("k"): return int(value[:-1]) * 1000
        return int(value)
    except ValueError:
        parser.error("Failure parsing '{}' as integer with unit".format(value))

def _print_bracket():
    print("-" * 80)
        
def _print_field(name, value):
    name = "{}:".format(name)
    print("{:<24} {}".format(name, value))
    
def _print_numeric_field(name, value, unit, fmt=None):
    name = "{}:".format(name)
    
    if fmt is not None:
        value = fmt.format(value)
    
    print("{:<24} {:>36} {}".format(name, value, unit))

class _Formatter(_argparse.ArgumentDefaultsHelpFormatter,
                 _argparse.RawDescriptionHelpFormatter):
    pass

class _PeriodicStatusThread(_threading.Thread):
    def __init__(self, command):
        _threading.Thread.__init__(self)

        self.command = command

        self.daemon = True
        self.parse_func = None
        
        self.messages = 0
        self.timeout_checkpoint = None # timestamp, messages

    def init(self):
        if self.command.operation == "send":
            self.parse_func = self.parse_send
        elif self.command.operation == "receive":
            self.parse_func = self.parse_receive
        else:
            raise Exception()
        
    def run(self):
        try:
            self.do_run()
        except QuiverError as e:
            exit("quiver-arrow: error: {}".format(e))
        except:
            _traceback.print_exc()
            exit(1)
        
    def do_run(self):
        self.command.started.wait()

        snap = _StatusSnapshot(self, None)

        self.timeout_checkpoint = snap.timestamp, self.messages

        with open(self.command.output_file, "r") as fin:
            while not self.command.ended.wait(1):
                transfers = self.collect_transfers(fin, self.parse_func)

                self.messages += len(transfers)

                snap.previous = None

                try:
                    snap = _StatusSnapshot(self, snap)
                except IOError:
                    break

                snap.capture_transfers(transfers)
                
                if self.command.operation == "receive" and not self.command.quiet:
                    snap.report()
                
                self.check_timeout(snap.timestamp)

    def collect_transfers(self, fin, parse_func):
        transfers = list()

        while True:
            fpos = fin.tell()
            line = fin.readline()

            if line == "" or line[-1] != "\n":
                fin.seek(fpos)
                break
            
            line = line[:-1]

            try:
                record = parse_func(line)
            except Exception as e:
                eprint("Failed to parse line '{}': {}".format(line, e))
                continue
            
            transfers.append(record)

        return transfers

    def parse_send(self, line):
        message_id, send_time = line.split(",", 1)
        send_time = long(send_time)

        return message_id, send_time

    def parse_receive(self, line):
        message_id, send_time, receive_time = line.split(",", 2)
        send_time = long(send_time)
        receive_time = long(receive_time)

        return message_id, send_time, receive_time

    def check_timeout(self, now):
        then, messages_then = self.timeout_checkpoint
        elapsed = now - then

        if self.messages == messages_then and elapsed > self.command.timeout:
            self.command.stop.set()

            operation = _string.capitalize(self.command.operation)
            eprint("{} operation timed out".format(operation))

            return

        if self.messages > messages_then:
            then = now
            
        self.timeout_checkpoint = then, self.messages

class _StatusSnapshot(object):
    def __init__(self, thread, previous):
        self.thread = thread
        self.previous = previous
        
        assert self.thread.command.proc is not None

        self.timestamp = _time.time()

        self.message_total = 0
        self.message_count = None
        self.message_rate = None
        self.message_latency = None

        self.capture_proc_info()

    def capture_proc_info(self):
        stat_file = "/proc/{}/stat".format(self.thread.command.proc.pid)

        with open(stat_file, "r") as f:
            stat_line = f.read()

        stat_fields = stat_line.split()
        self.stat_start_time = int(stat_fields[21])
        self.stat_utime = int(stat_fields[13]) + int(stat_fields[15])
        self.stat_stime = int(stat_fields[14]) + int(stat_fields[16])
        self.stat_rss = int(stat_fields[23])
        
    def capture_transfers(self, transfers):
        period = self.timestamp - self.previous.timestamp

        self.message_total = self.thread.messages
        self.message_count = len(transfers)
        self.message_rate = int(round(self.message_count / period))

        if self.message_count > 0 and self.thread.command.operation == "receive":
            latencies = list()

            for id, send_time, receive_time in transfers:
                latency = receive_time - send_time
                latencies.append(latency)

            self.message_latency = _numpy.mean(latencies)

    def report(self):
        assert self.previous is not None
        
        total = "{:,d}".format(self.message_total)
        rate = "{:,d} messages/s".format(self.message_rate)
        latency = "-"

        if self.message_latency is not None:
            latency = "{:,.1f} ms avg latency".format(self.message_latency)
        
        elapsed_seconds = self.timestamp - self.previous.timestamp
        prev_cpu_ticks = self.previous.stat_utime + self.previous.stat_stime
        curr_cpu_ticks = self.stat_utime + self.stat_stime
        cpu_seconds = float(curr_cpu_ticks - prev_cpu_ticks) / _user_hz
        cpu_percent = (cpu_seconds / elapsed_seconds) * 100
        cpu = "{:,.1f} %".format(cpu_percent)

        rss_mb = float(self.stat_rss * _page_size) / (1000 * 1024)
        rss = "{:,.1f} MB".format(rss_mb)

        args = total, rate, latency, cpu, rss
        line = "* {:>12} {:>24} {:>28} {:>10} {:>12}".format(*args)

        print(line)

def eprint(*args, **kwargs):
    args = ["{}: error:".format(_program)] + list(args)
    print(*args, file=_sys.stderr, **kwargs)

def _unique_id(length=16):
    assert length >= 1
    assert length <= 16

    uuid_bytes = _uuid.uuid4().bytes
    uuid_bytes = uuid_bytes[:length]

    return _binascii.hexlify(uuid_bytes).decode("utf-8")

_program = _os.path.split(_sys.argv[0])[1]
_user_hz = _os.sysconf(_os.sysconf_names["SC_CLK_TCK"])
_page_size = _resource.getpagesize()
