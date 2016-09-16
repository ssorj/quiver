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

import os as _os
import subprocess as _subprocess
import tempfile as _tempfile
import threading as _threading
import time as _time
import traceback as _traceback

class Command(object):
    def __init__(self, home_dir, output_dir, impl, mode, address,
                 operation, messages, bytes_, credit, timeout):
        self.home_dir = home_dir
        self.output_dir = output_dir
        self.impl = impl
        self.mode = mode
        self.address = address
        self.operation = operation
        self.messages = messages
        self.bytes_ = bytes_
        self.credit = credit
        self.timeout = timeout

        self.verbose = False
        self.quiet = False

        impl_name = "quiver-{}".format(self.impl)

        if self.output_dir is None:
            self.output_dir = _tempfile.mkdtemp(prefix="quiver-")
            
        self.impl_file = _os.path.join(self.home_dir, "exec", impl_name)
        self.transfers_file = _os.path.join(self.output_dir, "transfers.csv")

        self.started = _threading.Event()
        self.stopped = _threading.Event()

        self.periodic_status_thread = _PeriodicStatusThread(self)

    def init(self):
        if not _os.path.exists(self.output_dir):
            _os.makedirs(self.output_dir)
        
    def check(self):
        if not _os.path.exists(self.impl_file):
            raise Exception("No impl at '{}'".format(self.impl_file))

        if not _os.path.isdir(self.output_dir):
            raise Exception("Invalid output dir at '{}'".format(self.output_dir))

    def run(self):
        if self.address.startswith("//"):
            domain, path = self.address[2:].split("/", 1)
        else:
            domain, path = "localhost:5672", self.address

        args = [
            self.impl_file,
            self.output_dir,
            self.mode,
            domain,
            path,
            self.operation,
            str(self.messages),
            str(self.bytes_),
            str(self.credit),
        ]

        if self.verbose:
            print("Calling '{}'".format(" ".join(args)))

        if self.operation == "receive":
            self.periodic_status_thread.start()
        
        with open(self.transfers_file, "w") as fout:
            self.started.set()
            start_time = _time.time()

            _subprocess.check_call(args, stdout=fout)
            
            stop_time = _time.time()
            self.stopped.set()
            
        duration = stop_time - start_time

        if not self.quiet and self.operation == "receive":
            self.report()

    def report(self):
        if _os.path.getsize(self.transfers_file) == 0:
            raise Exception("No transfers")
        
        send_times = list()
        receive_times = list()
        latencies = list()

        with open(self.transfers_file, "r") as f:
            for line in f:
                message_id, send_time, receive_time = line.split(",", 2)

                send_time = float(send_time)
                receive_time = float(receive_time)
                latency = receive_time - send_time

                send_times.append(send_time)
                receive_times.append(receive_time)
                latencies.append(latency)

        duration = max(receive_times) - min(send_times)
        transfer_count = len(receive_times)
        transfer_rate = int(round(transfer_count / duration))
        latency_avg = sum(latencies) / transfer_count * 1000
        latency_min = min(latencies) * 1000
        latency_max = max(latencies) * 1000
        latency = "{:.1f}, {:.1f}, {:.1f}".format(latency_min, latency_max,
                                                  latency_avg)

        _print_bracket()
        _print_numeric_field("Duration", duration, "s", "{:.1f}")
        _print_numeric_field("Transfer count", transfer_count, "transfers", "{:,d}")
        _print_numeric_field("Transfer rate", transfer_rate, "transfers/s", "{:,d}")
        _print_numeric_field("Latency (min, max, avg)", latency, "ms")
        _print_bracket()

def _print_bracket():
    print("-" * 80)
        
def _print_numeric_field(name, value, unit, fmt=None):
    name = "{}:".format(name)
    
    if fmt is not None:
        value = fmt.format(value)
    
    print("{:<32} {:>24} {}".format(name, value, unit))
        
class _PeriodicStatusThread(_threading.Thread):
    def __init__(self, command):
        _threading.Thread.__init__(self)

        self.command = command

        self.transfers = 0
        self.intervals = 0
        self.checkpoint = None # timestamp, transfers
        
        self.daemon = True

    def run(self):
        try:
            self.do_run()
        except Exception as e:
            _traceback.print_exc()
            exit(str(e))
        
    def do_run(self):
        self.command.started.wait()
        
        self.checkpoint = _time.time(), self.transfers

        with open(self.command.transfers_file, "r") as fin:
            while not self.command.stopped.wait(1):
                # XXX separate reporting from stats collection
                self.print_status(fin)

                self.check_timeout()
                    
                self.intervals += 1

    def print_status(self, fin):
        send_times = list()
        receive_times = list()
        latencies = list()

        while True:
            fpos = fin.tell()
            line = fin.readline()

            if line == "" or line[-1] != "\n":
                fin.seek(fpos)
                break
            
            line = line[:-1]
            
            try:
                message_id, send_time, receive_time = line.split(",", 2)
            except ValueError:
                print("Failed to parse line '{}'".format(line))
                continue

            send_time = float(send_time)
            receive_time = float(receive_time)
            latency = receive_time - send_time

            send_times.append(send_time)
            receive_times.append(receive_time)
            latencies.append(latency)

        transfers = len(receive_times)
        self.transfers += transfers
        
        if transfers == 0:
            print("* {:12,}".format(self.transfers))
            return

        duration = max(receive_times) - min(send_times)
        rate = int(round(transfers / duration))
        latency = sum(latencies) / transfers * 1000

        rate_col = "{:10,} transfers/s".format(rate)
        latency_col = "{:.1f} ms avg latency".format(latency)
        
        print("* {:12,} {:>24} {:>24}".format(self.transfers, rate_col, latency_col))

    def check_timeout(self):
        now = _time.time()
        then, transfers_then = self.checkpoint

        if self.transfers == transfers_then and now - then > self.command.timeout:
            raise Exception("Timeout!")

        if self.transfers > transfers_then:
            then = now
            
        self.checkpoint = then, self.transfers
