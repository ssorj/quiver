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

class Command(object):
    def __init__(self, home_dir, output_dir, impl, mode, operation, address,
                 messages, bytes_, credit, timeout):
        self.home_dir = home_dir
        self.output_dir = output_dir
        self.impl = impl
        self.mode = mode
        self.operation = operation
        self.address = address
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
            self.operation,
            domain,
            path,
            str(self.messages),
            str(self.bytes_),
            str(self.credit),
            str(self.timeout),
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
                
        print("-" * 80)
        print("{:32} {:24.1f} s".format("Duration:", duration))
        print("{:32} {:24,} transfers".format("Transfer count:", transfer_count))
        print("{:32} {:24,} transfers/s".format("Transfer rate:", transfer_rate))
        print("{:32} {:>24} ms".format("Latency (min, max, avg):", latency))
        print("-" * 80)
    
class _PeriodicStatusThread(_threading.Thread):
    def __init__(self, command):
        _threading.Thread.__init__(self)

        self.command = command
        self.transfers = 0
        self.daemon = True

    def run(self):
        self.command.started.wait()
        
        with open(self.command.transfers_file, "r") as fin:
            while not self.command.stopped.wait(2):
                self.print_status(fin)

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
            print("* {:10,}".format(self.transfers))
            return

        duration = max(receive_times) - min(send_times)
        rate = int(round(transfers / duration))
        latency = sum(latencies) / transfers * 1000

        rate_col = "{:10,} transfers/s".format(rate)
        latency_col = "{:.1f} ms avg latency".format(latency)
        
        print("* {:10,} {:>20} {:>24}".format(self.transfers, rate_col, latency_col))
