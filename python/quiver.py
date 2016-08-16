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

from __future__ import print_function

import sys
import time

from qpid_messaging import *

class Operation(object):
    def __init__(self, type,
                 nconnections, nsessions, nlinks, nmessages, size,
                 verbose=True):
        assert type in ("send", "receive")

        self.type = type
        self.verbose = verbose

        self.nconnections = nconnections
        self.nsessions = nsessions
        self.nlinks = nlinks
        self.nmessages = nmessages
        self.size = size

        self.connections = list()
        self.sessions = list()
        self.links = list()
        self.messages = list()

    def log(self, text, *args):
        if self.verbose:
            print(text.format(*args))

    def run(self):
        self.setup()

        try:
            meth = getattr(self, self.type)
            meth()
        finally:
            self.teardown()

    def setup(self):
        self.log("Creating {} connections", self.nconnections)

        for i in range(self.nconnections):
            conn = Connection("localhost:5672", protocol="amqp1.0")
            self.connections.append(conn)

        self.log("Opening connections")

        for conn in self.connections:
            conn.open()

        self.log("Creating {} sessions", self.nsessions)

        for i in range(self.nsessions):
            conn = self.connections[i % len(self.connections)]
            session = conn.session()

            self.sessions.append(session)

        self.log("Creating {} links", self.nlinks)

        for i in range(self.nlinks):
            conn = self.connections[i % len(self.connections)]
            session = self.sessions[i % len(self.sessions)]

            if self.type == "send":
                link = session.sender("test")
            elif self.type == "receive":
                link = session.receiver("test")

            link.capacity = 1000

            self.links.append(link)

    def teardown(self):
        self.log("Closing connections")

        for conn in self.connections:
            conn.close()

    def send(self):
        self.log("Creating {} messages", self.nmessages)

        content = self.size * "x"

        for i in range(self.nmessages):
            message = Message(content)
            self.messages.append(message)

        self.log("Sending {} messages", len(self.messages))
        start = time.time()

        for i, message in enumerate(self.messages):
            link = self.links[i % len(self.links)]
            link.send(message)

        secs = time.time() - start
        rate = int(len(self.messages) / secs)

        self.log("Sent {} messages per second", rate)

    def receive(self):
        self.log("Receiving {} messages", self.nmessages)

        def loop():
            # XXX use self.messages
            count = 0

            while True:
                for link in self.links:
                    while link.available() > 0:
                        message = link.get()
                        count += 1

                        assert len(message.content) == self.size

                        link.session.acknowledge()

                        if count == self.nmessages:
                            return

        start = time.time()

        loop()

        secs = time.time() - start
        rate = int(self.nmessages / secs)

        self.log("Received {} messages per second", rate)
