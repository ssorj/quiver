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

import gzip as _gzip
import numpy as _numpy
import os as _os
import shutil as _shutil
import subprocess as _subprocess
import sys as _sys
import tempfile as _tempfile
import threading as _threading
import time as _time
import traceback as _traceback

#class QuiverCommand(object):
#    pass

class QuiverArrowCommand(object):
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

        self.quiet = False
        self.debug = False

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
        
        self.start_time = None
        self.end_time = None
        
        self.started = _threading.Event()
        self.stop = _threading.Event()
        self.ended = _threading.Event()

        self.periodic_status_thread = _PeriodicStatusThread(self)

    def init(self):
        if not _os.path.exists(self.output_dir):
            _os.makedirs(self.output_dir)
        
    def check(self):
        if not _os.path.exists(self.impl_file):
            msg = "No impl at '{}'".format(self.impl_file)
            raise QuiverError(msg)

        if not _os.path.isdir(self.output_dir):
            msg = "Invalid output dir at '{}'".format(self.output_dir)
            raise QuiverError(msg)

    def run(self):
        if self.address.startswith("//"):
            domain, path = self.address[2:].split("/", 1)
        else:
            domain, path = "localhost", self.address

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

        self.dprint("Calling '{}'", " ".join(args))

        if not self.quiet:
            self.print_config()

        if self.operation == "receive":
            self.periodic_status_thread.start()
        
        with open(self.transfers_file, "w") as fout:
            self.started.set()
            self.start_time = _time.time()

            proc = _subprocess.Popen(args, stdout=fout)

            self.dprint("Process {} ({}) started", proc.pid, self.operation)

            while proc.poll() == None:
                if self.stop.wait(0.1):
                    proc.terminate()

            if proc.returncode == 0:
                self.dprint("Process {} ({}) exited normally", proc.pid,
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

    def dprint(self, msg, *args):
        if not self.debug:
            return
        
        msg = "quiver: {}".format(msg)
        print(msg.format(*args))
            
    def print_config(self):
        _print_bracket()
        _print_field("Output dir", self.output_dir)
        _print_field("Implementation", self.impl)
        _print_field("Mode", self.mode)
        _print_field("Address", self.address)
        _print_field("Operation", self.operation)
        _print_field("Messages", "{:,d}".format(self.messages))
        _print_field("Bytes", "{:,d}".format(self.bytes_))
        _print_field("Credit", "{:,d}".format(self.credit))
        _print_field("Timeout", "{:,d}".format(self.timeout))
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

class QuiverError(Exception):
    pass

class _PeriodicStatusThread(_threading.Thread):
    def __init__(self, command):
        _threading.Thread.__init__(self)

        self.command = command

        self.transfers = 0
        self.period_start_time = None
        self.period_end_time = None
        self.timeout_checkpoint = None # timestamp, transfers
        
        self.daemon = True

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
        self.timeout_checkpoint = _time.time(), self.transfers

        with open(self.command.transfers_file, "r") as fin:
            while not self.command.ended.wait(1):
                # XXX separate reporting from stats collection
                self.print_status(fin)
                self.check_timeout()

    def print_status(self, fin):
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
                send_time = long(send_time)
                receive_time = long(receive_time)
            except ValueError as e:
                print("Failed to parse line '{}': {}".format(line, e))
                continue
            
            latency = long(receive_time) - long(send_time)
            latencies.append(latency)

        transfers = len(latencies)
        self.transfers += transfers
        
        if transfers == 0:
            if not self.command.quiet:
                print("* {:12,}".format(self.transfers))

            return

        self.period_start_time = self.period_end_time
        self.period_end_time = _time.time()
        
        duration = self.period_end_time - self.period_start_time
        rate = int(round(transfers / duration))
        latency = float(sum(latencies)) / transfers

        frate = "{:,d} messages/s".format(rate)
        flatency = "{:,.1f} ms avg latency".format(latency)

        if not self.command.quiet:
            msg = "* {:12,} {:>24} {:>28}".format \
                  (self.transfers, frate, flatency)
            print(msg)

    def check_timeout(self):
        now = _time.time()
        then, transfers_then = self.timeout_checkpoint
        elapsed = now - then

        if self.transfers == transfers_then and elapsed > self.command.timeout:
            self.command.stop.set()

            msg = "quiver: error: {} operation timed out".format \
                  (self.command.operation)
            eprint(msg)

            return

        if self.transfers > transfers_then:
            then = now
            
        self.timeout_checkpoint = then, self.transfers

def eprint(*args, **kwargs):
    print(*args, file=_sys.stderr, **kwargs)
