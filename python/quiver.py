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
import gzip as _gzip
import numpy as _numpy
import os as _os
import shutil as _shutil
import string as _string
import subprocess as _subprocess
import sys as _sys
import tempfile as _tempfile
import threading as _threading
import time as _time
import traceback as _traceback

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

_quiver_description = "Test the performance of messaging clients and servers"
_quiver_epilog = """
{}
example usage:
  $ qdrouterd &                   # Start a message server
  $ quiver q0                     # Start test
"""

_quiver_arrow_description = "Send or receive messages" # XXX Expand
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

_quiver_epilog = _quiver_epilog.lstrip()
_quiver_epilog = _quiver_epilog.format(_common_epilog)

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
    parser.add_argument("--server", action="store_true",
                        help="Operate in server mode")
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

        self.args = None
        
    def parse_args(self):
        self.args = self.parser.parse_args()

    def run(self):
        sender_count = 1 # max(args.pairs, args.senders)
        receiver_count = 1 # max(args.pairs, args.receivers)
        
        sender_args = ["quiver-arrow", "send", self.args.address]
        sender_args += _sys.argv[2:]

        receiver_args = ["quiver-arrow", "receive", self.args.address]
        receiver_args += _sys.argv[2:]

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

        self.impl = None
        self.mode = None
        self.operation = None
        self.address = None
        self.messages = None
        self.bytes_ = None
        self.credit = None
        self.output_dir = None
        self.timeout = 10
        self.quiet = False
        self.verbose = False

        self.impl_file = None
        self.transfers_file = None
        self.start_time = None
        self.end_time = None
        
        self.started = _threading.Event()
        self.stop = _threading.Event()
        self.ended = _threading.Event()

        self.parser = _argparse.ArgumentParser \
            (description=_quiver_arrow_description,
             epilog=_quiver_arrow_epilog,
             formatter_class=_Formatter)
        self.parser.add_argument("operation", metavar="OPERATION",
                                 choices=["send", "receive"],
                                 help="Either 'send' or 'receive'")
        _add_common_arguments(self.parser)
        
        self.periodic_status_thread = _PeriodicStatusThread(self)

    def parse_args(self):
        args = self.parser.parse_args()
        
        try:
            impl = _impls_by_name[args.impl]
        except KeyError:
            parser.error("Implementation '{}' is unknown".format(args.impl))

        mode = "server" if args.server else "client"

        messages = _parse_int_with_unit(self.parser, args.messages)
        bytes_ = _parse_int_with_unit(self.parser, args.bytes)
        credit = _parse_int_with_unit(self.parser, args.credit)
        
        self.impl = impl
        self.mode = mode
        self.operation = args.operation
        self.address = args.address
        self.messages = messages
        self.bytes_ = bytes_
        self.credit = credit
        self.output_dir = args.output
        self.timeout = args.timeout
        self.quiet = args.quiet
        self.verbose = args.verbose
    
    def init(self):
        impl_name = "arrow-{}".format(self.impl)

        if self.output_dir is None:
            self.output_dir = _tempfile.mkdtemp(prefix="quiver-")
            
        self.impl_file = _os.path.join(self.home_dir, "exec", impl_name)

        if self.operation == "send":
            self.transfers_file = _os.path.join(self.output_dir, "sent.csv")
        elif self.operation == "receive":
            self.transfers_file = _os.path.join(self.output_dir, "received.csv")
        else:
            raise Exception()
        
        if not _os.path.exists(self.output_dir):
            _os.makedirs(self.output_dir)

        self.periodic_status_thread.init()
            
    def check(self):
        if not _os.path.exists(self.impl_file):
            msg = "No impl at '{}'".format(self.impl_file)
            raise QuiverError(msg)

        if not _os.path.isdir(self.output_dir):
            msg = "Invalid output dir at '{}'".format(self.output_dir)
            raise QuiverError(msg)

    def run(self):
        self.periodic_status_thread.start()
        
        if self.address.startswith("//"):
            domain, path = self.address[2:].split("/", 1)
        else:
            domain, path = "localhost", self.address

        if ":" in domain:
            host, port = domain.split(":", 1)
        else:
            host, port = domain, "-"

        args = [
            self.impl_file,
            self.output_dir,
            self.mode,
            self.operation,
            host,
            port,
            path,
            str(self.messages),
            str(self.bytes_),
            str(self.credit),
        ]

        self.vprint("Calling '{}'", " ".join(args))

        if not self.quiet:
            self.print_config()

        with open(self.transfers_file, "w") as fout:
            self.started.set()
            self.start_time = _time.time()

            proc = _subprocess.Popen(args, stdout=fout)

            self.vprint("Process {} ({}) started", proc.pid, self.operation)

            while proc.poll() == None:
                if self.stop.wait(0.1):
                    proc.terminate()

            if proc.returncode == 0:
                self.vprint("Process {} ({}) exited normally", proc.pid,
                            self.operation)
            else:
                msg = "Process {} ({}) exited with code {}".format \
                      (proc.pid, self.operation, proc.returncode)
                raise QuiverError(msg)
                    
            self.end_time = _time.time()
            self.ended.set()

        if self.operation == "receive":
            if _os.path.getsize(self.transfers_file) == 0:
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
        _print_field("Output dir", self.output_dir)
        _print_field("Implementation", self.impl)
        _print_field("Mode", self.mode)
        _print_field("Operation", self.operation)
        _print_field("Address", self.address)
        _print_field("Messages", "{:,d}".format(self.messages))
        _print_field("Bytes", "{:,d}".format(self.bytes_))
        _print_field("Credit", "{:,d}".format(self.credit))
        #_print_field("Timeout", "{:,d}".format(self.timeout))
        _print_bracket()
            
    def print_results(self):
        latencies = list()

        with open(self.transfers_file, "r") as f:
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
        with open(self.transfers_file, "rb") as fin:
            with _gzip.open("{}.gz".format(self.transfers_file), "wb") as fout:
                _shutil.copyfileobj(fin, fout)

        _os.remove(self.transfers_file)

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

        self.parse_func = None
        
        self.transfers = 0
        self.period_start_time = None
        self.period_end_time = None
        self.timeout_checkpoint = None # timestamp, transfers

        self.daemon = True

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
            exit("quiver: error: {}".format(e))
        except:
            _traceback.print_exc()
            exit(1)
        
    def do_run(self):
        self.command.started.wait()

        self.period_end_time = _time.time()
        self.timeout_checkpoint = self.period_end_time, self.transfers

        with open(self.command.transfers_file, "r") as fin:
            while not self.command.ended.wait(1):
                transfers = self.collect_transfers(fin, self.parse_func)

                self.transfers += len(transfers)
                self.period_start_time = self.period_end_time
                self.period_end_time = _time.time()

                self.check_timeout(self.period_end_time)

                if self.command.operation == "receive" and not self.command.quiet:
                    self.print_status(transfers)
                
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
                print("Failed to parse line '{}': {}".format(line, e))
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

    def print_status(self, transfers):
        count = len(transfers)

        if count == 0:
            print("* {:12,}".format(self.transfers))
            return
        
        latencies = list()

        for id, send_time, receive_time in transfers:
            latency = receive_time - send_time
            latencies.append(latency)

        duration = self.period_end_time - self.period_start_time
        rate = int(round(count / duration))
        latency = float(sum(latencies)) / count

        rate = "{:,d} messages/s".format(rate)
        latency = "{:,.1f} ms avg latency".format(latency)

        args = self.transfers, rate, latency
        msg = "* {:12,} {:>24} {:>28}".format(*args)

        print(msg)

    def check_timeout(self, now):
        then, transfers_then = self.timeout_checkpoint
        elapsed = now - then

        if self.transfers == transfers_then and elapsed > self.command.timeout:
            self.command.stop.set()

            operation = _string.capitalize(self.command.operation)
            msg = "quiver: error: {} operation timed out".format(operation)
            eprint(msg)

            return

        if self.transfers > transfers_then:
            then = now
            
        self.timeout_checkpoint = then, self.transfers

def eprint(*args, **kwargs):
    print(*args, file=_sys.stderr, **kwargs)
