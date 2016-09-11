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

import threading as _threading

class PeriodicStatusThread(_threading.Thread):
    def __init__(self, start_event, stop_event, transfers_file):
        _threading.Thread.__init__(self)

        self.start_event = start_event
        self.stop_event = stop_event
        self.transfers_file = transfers_file

        self.transfers = 0
        
        self.daemon = True

    def run(self):
        total_transfers = 0
        
        self.start_event.wait()
        
        with open(self.transfers_file, "r") as fin:
            while not self.stop_event.wait(2):
                self.print_status(fin)

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
