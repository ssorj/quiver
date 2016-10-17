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
import json as _json
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
  rhea [javascript]               Client mode only at the moment
  vertx-proton [java]             Client mode only
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
                        default="10")
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

class _Command(object):
    def __init__(self, home_dir):
        self.home_dir = home_dir

        self.parser = None
        self.verbose = False
        self.quiet = False
        
    def parse_int_with_unit(self, value):
        assert self.parser is not None
        
        try:
            if value.endswith("m"): return int(value[:-1]) * 1000 * 1000
            if value.endswith("k"): return int(value[:-1]) * 1000
            return int(value)
        except ValueError:
            msg = "Failure parsing '{}' as integer with unit".format(value)
            self.parser.error(msg)

    def vprint(self, message, *args, **kwargs):
        if not self.verbose:
            return
        
        message = "{}: {}".format(_program, message)
        print(message.format(*args), **kwargs)

class QuiverCommand(_Command):
    def __init__(self, home_dir):
        super(QuiverCommand, self).__init__(home_dir)

        self.parser = _argparse.ArgumentParser \
            (description=_quiver_description,
             epilog=_quiver_epilog,
             formatter_class=_Formatter)

        _add_common_arguments(self.parser)

        self.start_time = None
        self.end_time = None
        
    def init(self):
        args = self.parser.parse_args()

        self.address = args.address
        self.output_dir = args.output
        self.messages = self.parse_int_with_unit(args.messages)
        self.bytes_ = self.parse_int_with_unit(args.bytes)
        self.credit = self.parse_int_with_unit(args.credit)
        self.timeout = self.parse_int_with_unit(args.timeout)
        
        self.init_only = args.init_only

        if self.output_dir is None:
            self.output_dir = _make_temp_dir()

    def run(self):
        args = _sys.argv[2:]

        if "--output" not in args:
            args += "--output", self.output_dir
        
        sender_args = ["quiver-arrow", "send", self.address]
        sender_args += args
        sender_snaps = _join(self.output_dir, "sender-snapshots.csv")

        receiver_args = ["quiver-arrow", "receive", self.address]
        receiver_args += args
        receiver_snaps = _join(self.output_dir, "receiver-snapshots.csv")

        _touch(sender_snaps)
        _touch(receiver_snaps)

        self.start_time = _timestamp()
        
        receiver = _subprocess.Popen(receiver_args)
        _time.sleep(0.1) # XXX Instead, wait for receiver readiness
        sender = _subprocess.Popen(sender_args)

        self.print_status_headings()

        carried_ssnap = None
        carried_rsnap = None
            
        with open(sender_snaps) as fs, open(receiver_snaps) as fr:
            while receiver.poll() == None:
                _time.sleep(0.5)
                    
                ssnap = _read_whole_line(fs)
                rsnap = _read_whole_line(fr)

                #print("S:", ssnap)
                #print("R:", rsnap)

                if ssnap is not None:
                    carried_ssnap = ssnap

                if carried_ssnap is None and sender.poll() is not None:
                    carried_ssnap = "-"

                if rsnap is not None:
                    carried_rsnap = rsnap

                if None in (carried_ssnap, carried_rsnap):
                    continue

                self.print_status(carried_ssnap, carried_rsnap)

                carried_ssnap, carried_rsnap = None, None

        sender.wait()
        receiver.wait()

        self.end_time = _timestamp()

        # XXX
        #self.print_summary()

    columns = "{:>8}  {:>10}  {:>10}  {:>8}  {:>8}  {:>10}  {:>10}  {:>8}  {:>8}"

    heading_row_1 = "{:-^8}  {:-^42}  {:-^42}".format("", " Sender ", " Receiver ")
    heading_row_2 = columns.format \
        ("Time [s]",
         "Total [m]", "Rate [m/s]", "CPU [%]", "RSS [M]",
         "Total [m]", "Rate [m/s]", "CPU [%]", "RSS [M]")
    heading_row_3 = "{:>8}  {:>42}  {:>42}".format("-" * 8, "-" * 42, "-" * 42)
        
    def print_status_headings(self):
        print(self.heading_row_1)
        print(self.heading_row_2)
        print(self.heading_row_3)
        
    def print_status(self, ssnap, rsnap):
        if ssnap == "-":
            stotal, srate, scpu, srss = "-", "-", "-", "-"
        else:
            ssnap = map(int, ssnap.split(","))
            sts, speriod, stotal, scount, sutime, sstime, srss = ssnap

            srate = scount / (float(speriod) / 1000)
            srss = float(srss) / (1000 * 1024)

            stotal = "{:,d}".format(stotal)
            srate = "{:,.0f}".format(srate)
            srss = "{:,.1f}".format(srss)
        
        rsnap = map(int, rsnap.split(","))
        rts, rperiod, rtotal, rcount, rutime, rstime, rrss, latency = rsnap

        time = float(rts - self.start_time) / 1000
        time = "{:,.1f}".format(time)
        
        rrate = rcount / (float(rperiod) / 1000)
        rrss = float(rrss) / (1000 * 1024)

        rtotal = "{:,d}".format(rtotal)
        rrate = "{:,.0f}".format(rrate)
        rrss = "{:,.1f}".format(rrss)
        
        line = self.columns.format \
               (time,
                stotal, srate, "-", srss,
                rtotal, rrate, "-", rrss)
        
        print(line)
        
    def print_summary(self):
        print("-" * 80)
        print()

        print("# Quiver summary of run X #")
        print()

        print("## Configuration ##")
        print()

        _print_field("Address", self.address)
        _print_field("Output dir", self.output_dir)
        _print_numeric_field("Messages", self.messages, "messages")
        _print_numeric_field("Payload size", self.bytes_, "bytes")
        _print_numeric_field("Credit window", self.credit, "messages")
        _print_numeric_field("Timeout", self.timeout, "s")

        print()
        print("## Sender ##")
        print()

        _print_field("ID", "XXX")
        _print_field("Implementation", "XXX")
        _print_numeric_field("Message rate", 0, "messages/s")
        _print_numeric_field("Average latency", 0, "ms")
        _print_numeric_field("Average CPU", 0, "%")
        _print_numeric_field("Max RSS", 0, "MB")
        
        print()
        print("## Receiver ##")
        print()

        _print_field("ID", "XXX")
        _print_field("Implementation", "XXX")
        _print_numeric_field("Message rate", 0, "messages/s")
        _print_numeric_field("Average latency", 0, "ms")
        _print_numeric_field("Average CPU", 0, "%")
        _print_numeric_field("Max RSS", 0, "MB")
        
        print()
        print("## Overall ##")
        print()

        _print_numeric_field("Duration", 0, "s")
        _print_numeric_field("Message count", 0, "messages")
        _print_numeric_field("Message rate", 0, "messages/s")
        _print_numeric_field("Average latency", 0, "ms")
        _print_numeric_field("Latency 25, 50, 75, 100%", 0, "ms")
        _print_numeric_field("Latency 99, 99.9, 99.99%", 0, "ms")

        print()
        print("-" * 80)
        
class QuiverArrowCommand(_Command):
    def __init__(self, home_dir):
        super(QuiverArrowCommand, self).__init__(home_dir)
        
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

        messages = self.parse_int_with_unit(args.messages)
        bytes_ = self.parse_int_with_unit(args.bytes)
        credit = self.parse_int_with_unit(args.credit)
        timeout = self.parse_int_with_unit(args.timeout)
        
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
        self.timeout = timeout
        self.quiet = args.quiet
        self.verbose = args.verbose
        
        if args.server:
            self.connection_mode = "server"
            self.channel_mode = "passive"

        if args.passive:
            self.channel_mode = "passive"
        
        if self.output_dir is None:
            self.output_dir = _make_temp_dir()
            
        if not _os.path.exists(self.output_dir):
            _os.makedirs(self.output_dir)

        impl_name = "arrow-{}".format(self.impl)
        self.impl_file = "{}/exec/{}".format(self.home_dir, impl_name)

        if self.operation == "send":
            self.snapshots_file = _join(self.output_dir, "sender-snapshots.csv")
            self.summary_file = _join(self.output_dir, "sender-summary.json")
            self.transfers_file = _join(self.output_dir, "sender-transfers.csv")
        elif self.operation == "receive":
            self.snapshots_file = _join(self.output_dir, "receiver-snapshots.csv")
            self.summary_file = _join(self.output_dir, "receiver-summary.json")
            self.transfers_file = _join(self.output_dir, "receiver-transfers.csv")
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

        with open(self.transfers_file, "w") as fout:
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

        if _os.path.getsize(self.transfers_file) == 0:
            raise QuiverError("No transfers")

        if self.operation == "send":
            self.compute_sender_results()
        elif self.operation == "receive":
            self.compute_receiver_results()
            
            if not self.quiet:
                self.print_results()
        else:
            raise Exception()

        self.save_summary()

        _compress_file(self.transfers_file)

    def compute_sender_results(self):
        count = 0
        
        with open(self.transfers_file, "r") as f:
            for line in f:
                message_id, send_time = _parse_send(line)
                count += 1

        duration = self.end_time - self.start_time

        self.message_count = count
        self.message_rate = int(round(self.message_count / duration))
        self.latency_average = None
        self.latency_quartiles = None
        self.latency_nines = None
        
    def compute_receiver_results(self):
        latencies = list()

        with open(self.transfers_file, "r") as f:
            for line in f:
                message_id, send_time, receive_time = _parse_receive(line)

                send_time = long(send_time)
                receive_time = long(receive_time)
                latency = receive_time - send_time

                latencies.append(latency)

        duration = self.end_time - self.start_time

        self.message_count = len(latencies)
        self.message_rate = int(round(self.message_count / duration))

        values = (25, 50, 75, 100, 99, 99.9, 99.99, 99.999)
        percentiles = _numpy.percentile(latencies, values)
        
        self.latency_average = _numpy.mean(latencies)
        self.latency_quartiles = list(percentiles[:4])
        self.latency_nines = list(percentiles[4:])
        
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
                "payload_size": self.bytes_, # XXX
                "credit_window": self.credit, # XXX
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

        with open(self.summary_file, "w") as f:
            _json.dump(props, f, indent=2)
        
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

        percentiles = (25, 50, 75, 100, 99, 99.9, 99.99)
        results = _numpy.percentile(latencies, percentiles)
        quartiles = "{:,.0f} | {:,.0f} | {:,.0f} | {:,.0f}".format(*results[:4])
        nines = "{:,.0f} | {:,.0f} | {:,.0f}".format(*results[4:])
        
        _print_bracket()
        _print_numeric_field("Duration", duration, "s", "{:,.1f}")
        _print_numeric_field("Message count", transfers, "messages", "{:,d}")
        _print_numeric_field("Message rate", rate, "messages/s", "{:,d}")
        _print_numeric_field("Latency average", latency, "ms", "{:,.1f}")
        _print_numeric_field("Latency quartiles", quartiles, "ms")
        _print_numeric_field("Latency nines", nines, "ms")
        _print_bracket()

class _Formatter(_argparse.ArgumentDefaultsHelpFormatter,
                 _argparse.RawDescriptionHelpFormatter):
    pass

class _PeriodicStatusThread(_threading.Thread):
    def __init__(self, command):
        _threading.Thread.__init__(self)

        self.command = command

        self.timeout_checkpoint = None
        self.daemon = True

    def run(self):
        try:
            self.do_run()
        except QuiverError as e:
            eprint(e)
            _sys.exit(1)
        except:
            _traceback.print_exc()
            _sys.exit(1)
        
    def do_run(self):
        if self.command.operation == "send":
            parse_func = _parse_send
        elif self.command.operation == "receive":
            parse_func = _parse_receive
        else:
            raise Exception()
        
        self.command.started.wait()

        snap = _StatusSnapshot(self, None)
        self.timeout_checkpoint = snap

        with open(self.command.transfers_file, "r") as f:
            while not self.command.ended.wait(1):
                snap.previous = None

                try:
                    snap = _StatusSnapshot(self, snap)
                except IOError:
                    eprint(e)
                    break

                snap.capture_proc_info()
                snap.capture_transfers(f, parse_func)
                snap.save()
                
                self.check_timeout(snap)

    def check_timeout(self, now):
        then = self.timeout_checkpoint
        elapsed = float(now.timestamp - then.timestamp) / 1000

        if now.total == then.total and elapsed > self.command.timeout:
            self.command.stop.set()

            operation = _string.capitalize(self.command.operation)
            eprint("{} operation timed out", operation)

            return

        if now.total > then.total:
            self.timeout_checkpoint = now
        
class _StatusSnapshot(object):
    def __init__(self, thread, previous):
        self.thread = thread
        self.previous = previous
        
        assert self.thread.command.proc is not None

        self.timestamp = _timestamp()
        self.period = 0

        if self.previous is not None:
            self.period = self.timestamp - self.previous.timestamp

        self.total = 0
        self.count = None
        self.latency = None

    def capture_proc_info(self):
        file_ = _join("/", "proc", str(self.thread.command.proc.pid), "stat")

        with open(file_, "r") as f:
            line = f.read()

        fields = line.split()

        self.utime = (int(fields[13]) + int(fields[15])) * _ticks_per_second / 1000
        self.stime = (int(fields[14]) + int(fields[16])) * _ticks_per_second / 1000
        self.rss = int(fields[23]) * _page_size
        
    def capture_transfers(self, transfers_file, parse_func):
        transfers = list()

        while True:
            line = _read_whole_line(transfers_file)

            if line is None:
                break

            try:
                record = parse_func(line)
            except Exception as e:
                eprint("Failed to parse line '{}': {}", line, str(e))
                continue
            
            transfers.append(record)
        
        self.count = len(transfers)
        self.total = self.previous.total + self.count

        if self.count > 0 and self.thread.command.operation == "receive":
            latencies = list()

            for id, send_time, receive_time in transfers:
                latency = receive_time - send_time
                latencies.append(latency)

            self.latency = int(_numpy.mean(latencies))

    # def report(self):
    #     assert self.previous is not None
        
    #     total = "{:,d}".format(self.total)
    #     rate = "{:,d} messages/s".format(self.rate)
    #     latency = "-"

    #     if self.latency is not None:
    #         latency = "{:,.1f} ms avg latency".format(self.latency)
        
    #     elapsed_seconds = float(self.timestamp - self.previous.timestamp) / 1000
    #     prev_cpu_seconds = float(self.previous.utime + self.previous.stime) / 1000
    #     curr_cpu_seconds = float(self.utime + self.stime) / 1000

    #     cpu_seconds = curr_cpu_seconds - prev_cpu_seconds
    #     cpu_percent = (cpu_seconds / elapsed_seconds) * 100
    #     cpu = "{:,.1f} %".format(cpu_percent)

    #     rss_mb = float(self.rss) / (1000 * 1024)
    #     rss = "{:,.1f} MB".format(rss_mb)

    #     args = total, rate, latency, cpu, rss
    #     line = "* {:>12} {:>24} {:>28} {:>10} {:>12}".format(*args)

    #     #print(line)

    def save(self):
        args = [
            self.timestamp,
            self.period,
            self.total,
            self.count,
            self.utime,
            self.stime,
            self.rss,
        ]

        if self.latency is not None:
            args.append(self.latency)

        args = map(str, args)
        line = "{}\n".format(",".join(args))

        with open(self.thread.command.snapshots_file, "a") as f:
            f.write(line)

def eprint(message, *args, **kwargs):
    if isinstance(message, Exception):
        message = str(message)
    
    message = "{}: {}".format(_program, message)
    message = message.format(*args)

    print(message, file=_sys.stderr, **kwargs)

def _parse_send(line):
    message_id, send_time = line.split(",", 1)
    send_time = long(send_time)

    return message_id, send_time

def _parse_receive(line):
    message_id, send_time, receive_time = line.split(",", 2)
    send_time = long(send_time)
    receive_time = long(receive_time)

    return message_id, send_time, receive_time

def _print_bracket():
    print("-" * 80)

def _print_field(name, value):
    name = "{}:".format(name)
    print("    {:<24} {}".format(name, value))
    
def _print_numeric_field(name, value, unit, fmt=None):
    name = "{}:".format(name)
    
    if fmt is not None:
        value = fmt.format(value)
    
    print("    {:<24} {:>32} {}".format(name, value, unit))
    
def _timestamp():
    return int(_time.time() * 1000)

def _unique_id(length=16):
    assert length >= 1
    assert length <= 16

    uuid_bytes = _uuid.uuid4().bytes
    uuid_bytes = uuid_bytes[:length]

    return _binascii.hexlify(uuid_bytes).decode("utf-8")

def _make_temp_dir():
    return _tempfile.mkdtemp(prefix="quiver-")

def _touch(path):
    with open(path, "a") as f:
        f.write("")

def _read_whole_line(file):
    fpos = file.tell()
    line = file.readline()

    if line == "" or line[-1] != "\n":
        file.seek(fpos)
        return
    
    return line[:-1]
            
def _compress_file(path):
    args = "xz", "--compress", "-0", "--threads", "0", path
    _subprocess.check_call(args)

_join = _os.path.join

_program = _os.path.split(_sys.argv[0])[1]
_ticks_per_second = _os.sysconf(_os.sysconf_names["SC_CLK_TCK"])
_page_size = _resource.getpagesize()
