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

import collections as _collections
import os as _os
import proton as _proton
import proton.handlers as _handlers
import proton.reactor as _reactor
import uuid as _uuid
import shutil as _shutil
import subprocess as _subprocess
import sys as _sys
import time as _time
import tempfile as _tempfile

class Broker(object):
    def __init__(self, host, port, id=None, user=None, password=None, ready_file=None):
        self.host = host
        self.port = port
        self.id = id
        self.user = user
        self.password = password
        self.ready_file = ready_file

        if self.id is None:
            self.id = "broker-{0}".format(_uuid.uuid4())

        self.container = _reactor.Container(_Handler(self), self.id)

        self._config_dir = None

    def init(self):
        if self.user is not None:
            if self.password is None:
                self.fail("A password is required for user authentication")

            self._init_sasl_config()

    def _init_sasl_config(self):
        self._config_dir = _tempfile.mkdtemp(prefix="brokerlib-", suffix="")
        config_file = _os.path.join(self._config_dir, "proton-server.conf")
        sasldb_file = _os.path.join(self._config_dir, "users.sasldb")

        _os.environ["PN_SASL_CONFIG_PATH"] = self._config_dir

        with open(config_file, "w") as f:
            f.write("sasldb_path: {0}\n".format(sasldb_file))
            f.write("mech_list: PLAIN SCRAM-SHA-1\n")

        command = "echo '{0}' | saslpasswd2 -p -f {1} '{2}'".format \
                  (self.password, sasldb_file, self.user)

        try:
            _subprocess.check_call(command, shell=True)
        except _subprocess.CalledProcessError as e:
            self.fail("Failed adding user to SASL database: {0}", e)

    def info(self, message, *args):
        pass

    def notice(self, message, *args):
        pass

    def warn(self, message, *args):
        pass

    def error(self, message, *args):
        _sys.stderr.write("{0}\n".format(message.format(*args)))
        _sys.stderr.flush()

    def fail(self, message, *args):
        self.error(message, *args)
        _sys.exit(1)

    def run(self):
        self.container.run()

        if _os.path.exists(self._config_dir):
            _shutil.rmtree(self.dir, ignore_errors=True)

class _Queue(object):
    def __init__(self, broker, address):
        self.broker = broker
        self.address = address

        self.messages = _collections.deque()
        self.consumers = _collections.deque()

        self.broker.info("Created {0}", self)

    def __repr__(self):
        return "queue '{0}'".format(self.address)

    def add_consumer(self, link):
        assert link.is_sender
        assert link not in self.consumers

        self.consumers.append(link)

        self.broker.info("Added consumer for {0} to {1}", link.connection, self)

    def remove_consumer(self, link):
        assert link.is_sender

        try:
            self.consumers.remove(link)
        except ValueError:
            return

        self.broker.info("Removed consumer for {0} from {1}", link.connection, self)

    def store_message(self, delivery, message):
        self.messages.append(message)

        self.broker.notice("Stored {0} from {1} on {2}", message, delivery.connection, self)

    def forward_messages(self):
        credit = sum([x.credit for x in self.consumers])
        sent = 0

        if credit == 0:
            return

        while sent < credit:
            for consumer in self.consumers:
                if consumer.credit == 0:
                    continue

                try:
                    message = self.messages.popleft()
                except IndexError:
                    self.consumers.rotate(sent)
                    return

                consumer.send(message)
                sent += 1

                self.broker.notice("Forwarded {0} on {1} to {2}", message, self, consumer.connection)

        self.consumers.rotate(sent)

class _Handler(_handlers.MessagingHandler):
    def __init__(self, broker):
        super(_Handler, self).__init__()

        self.broker = broker
        self.queues = dict()
        self.verbose = False

    def on_start(self, event):
        interface = "{0}:{1}".format(self.broker.host, self.broker.port)

        self.acceptor = event.container.listen(interface)

        self.broker.notice("Listening for connections on '{0}'", interface)

        if self.broker.ready_file is not None:
            _time.sleep(0.1) # XXX
            with open(self.broker.ready_file, "w") as f:
                f.write("ready\n")

    def get_queue(self, address):
        try:
            queue = self.queues[address]
        except KeyError:
            queue = self.queues[address] = _Queue(self.broker, address)

        return queue

    def on_link_opening(self, event):
        if event.link.is_sender:
            if event.link.remote_source.dynamic:
                address = "{0}/{1}".format(event.connection.remote_container, event.link.name)
            else:
                address = event.link.remote_source.address

            assert address is not None

            event.link.source.address = address

            queue = self.get_queue(address)
            queue.add_consumer(event.link)

        if event.link.is_receiver:
            address = event.link.remote_target.address
            event.link.target.address = address

    def on_link_closing(self, event):
        if event.link.is_sender:
            queue = self.queues[event.link.source.address]
            queue.remove_consumer(event.link)

    def on_connection_opening(self, event):
        # XXX I think this should happen automatically
        event.connection.container = event.container.container_id

    def on_connection_opened(self, event):
        self.broker.notice("Opened connection from {0}", event.connection)

    def on_connection_closing(self, event):
        self.remove_consumers(event.connection)

    def on_connection_closed(self, event):
        self.broker.notice("Closed connection from {0}", event.connection)

    def on_disconnected(self, event):
        self.broker.notice("Disconnected from {0}", event.connection)

        self.remove_consumers(event.connection)

    def remove_consumers(self, connection):
        link = connection.link_head(_proton.Endpoint.REMOTE_ACTIVE)

        while link is not None:
            if link.is_sender:
                queue = self.queues[link.source.address]
                queue.remove_consumer(link)

            link = link.next(_proton.Endpoint.REMOTE_ACTIVE)

    def on_link_flow(self, event):
        if event.link.is_sender and event.link.drain_mode:
            event.link.drained()

    def on_sendable(self, event):
        queue = self.get_queue(event.link.source.address)
        queue.forward_messages()

    def on_settled(self, event):
        template = "Container '{0}' {1} {2} to {3}"
        container = event.connection.remote_container
        source = event.link.source
        delivery = event.delivery

        if delivery.remote_state == delivery.ACCEPTED:
            self.broker.info(template, container, "accepted", delivery, source)
        elif delivery.remote_state == delivery.REJECTED:
            self.broker.warn(template, container, "rejected", delivery, source)
        elif delivery.remote_state == delivery.RELEASED:
            self.broker.notice(template, container, "released", delivery, source)
        elif delivery.remote_state == delivery.MODIFIED:
            self.broker.notice(template, container, "modified", delivery, source)

    def on_message(self, event):
        message = event.message
        delivery = event.delivery
        address = event.link.target.address

        if address is None:
            address = message.address

        queue = self.get_queue(address)
        queue.store_message(delivery, message)
        queue.forward_messages()

if __name__ == "__main__":
    def _print(message, *args):
        message = message.format(*args)
        _sys.stderr.write("{0}\n".format(message))
        _sys.stderr.flush()

    class _Broker(Broker):
        def info(self, message, *args): _print(message, *args)
        def notice(self, message, *args): _print(message, *args)
        def warn(self, message, *args): _print(message, *args)

    try:
        host, port = _sys.argv[1:3]
    except IndexError:
        _print("Usage: brokerlib <host> <port>")
        _sys.exit(1)

    try:
        port = int(port)
    except ValueError:
        _print("The port must be an integer")
        _sys.exit(1)

    broker = _Broker(host, port)

    try:
        broker.run()
    except KeyboardInterrupt:
        pass
