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

import collections as _collections
import plano as _plano
import proton as _proton
import proton.handlers as _handlers
import proton.reactor as _reactor
import shlex as _shlex
import subprocess as _subprocess

from .common import *

_description = """
Start a message server with the given queue.
"""

_epilog = """
URLs:
  [//DOMAIN/]PATH                 The default domain is 'localhost'
  //example.net/jobs
  //10.0.0.10:5672/jobs/alpha
  //localhost/q0
  q0

server implementations:
  activemq
  activemq-artemis [artemis]
  qpid-cpp [qpidd]
  qpid-dispatch [dispatch, qdrouterd]
"""

class QuiverServerCommand(Command):
    def __init__(self, home_dir):
        super(QuiverServerCommand, self).__init__(home_dir)

        self.parser.description = _description.lstrip()
        self.parser.epilog = _epilog.lstrip()

        self.parser.add_argument("url", metavar="URL",
                                 help="The location of a message queue")
        self.parser.add_argument("--impl", metavar="NAME",
                                 help="Use NAME implementation",
                                 default="builtin")
        self.parser.add_argument("--ready-file", metavar="FILE",
                                 help="File used to indicate the server is ready")
        self.parser.add_argument("--prelude", metavar="PRELUDE", default="",
                                 help="Commands to precede the impl invocation")

        self.add_common_tool_arguments()

    def init(self):
        super(QuiverServerCommand, self).init()

        self.impl = self.get_server_impl_name(self.args.impl, self.args.impl)
        self.ready_file = self.args.ready_file
        self.prelude = _shlex.split(self.args.prelude)
        self.init_only = self.args.init_only
        self.quiet = self.args.quiet
        self.verbose = self.args.verbose

        self.impl_file = self.get_server_impl_file(self.impl)

        if not _plano.exists(self.impl_file):
            raise CommandError("No implementation at '{}'", self.impl_file)

        if self.ready_file is None:
            self.ready_file = "-"

        self.init_url_attributes()

    def run(self):
        args = self.prelude + [
            self.impl_file,
            self.host,
            self.port,
            self.path,
            self.ready_file,
        ]

        assert None not in args, args

        _plano.call(args)

class BuiltinBroker(object):
    def __init__(self, host, port, path, ready_file):
        self.host = host
        self.port = port
        self.path = path
        self.ready_file = ready_file

    def run(self):
        handler = _BrokerHandler(self)
        container = _reactor.Container(handler)
        container.container_id = "quiver-server-builtin"

        container.run()

class _BrokerHandler(_handlers.MessagingHandler):
    def __init__(self, broker):
        super(_BrokerHandler, self).__init__()

        self.broker = broker

        self.queues = dict()

    def on_start(self, event):
        domain = "{}:{}".format(self.broker.host, self.broker.port)

        event.container.listen(domain)

        _plano.notice("Listening on '{}'", domain)

        if self.broker.ready_file != "-":
            _plano.write(self.broker.ready_file, "ready\n")

    def get_queue(self, address):
        try:
            queue = self.queues[address]
        except KeyError:
            queue = self.queues[address] = _Queue(address)

        return queue

    def on_link_opening(self, event):
        # XXX check that address matches config

        if event.link.is_sender:
            if event.link.remote_source.dynamic:
                address = str(uuid.uuid4())
            else:
                address = event.link.remote_source.address

            assert address is not None

            event.link.source.address = address

            queue = self.get_queue(address)
            queue.add_consumer(event.link)

        if event.link.is_receiver:
            address = event.link.remote_target.address

            # XXX Fails with qpid-jms
            #assert address is not None

            event.link.target.address = address

    def on_link_closing(self, event):
        if event.link.is_sender:
            queue = self.queues[link.source.address]
            queue.remove_consumer(link)

    def on_connection_opening(self, event):
        _plano.notice("Opening connection from '{}'", event.connection.remote_container)

        # XXX I think this should happen automatically
        event.connection.container = event.container.container_id

    def on_connection_closing(self, event):
        _plano.notice("Closing connection from '{}'", event.connection.remote_container)

        self.remove_consumers(event.connection)

    def on_disconnected(self, event):
        _plano.notice("Disconnected from {}", event.connection.remote_container)

        self.remove_consumers(event.connection)

    def remove_consumers(self, connection):
        link = connection.link_head(_proton.Endpoint.REMOTE_ACTIVE)

        while link is not None:
            if link.is_sender:
                queue = self.queues[link.source.address]
                queue.remove_consumer(link)

            link = link.next(_proton.Endpoint.REMOTE_ACTIVE)

    def on_sendable(self, event):
        queue = self.get_queue(event.link.source.address)
        queue.forward_messages(event.link)

    def on_message(self, event):
        queue = self.get_queue(event.link.target.address)
        queue.store_message(event.message)

        for link in queue.consumers:
            queue.forward_messages(link)

class _Queue(object):
    def __init__(self, address):
        self.address = address

        self.messages = _collections.deque()
        self.consumers = list()

        _plano.notice("Creating {}", self)

    def __repr__(self):
        return "queue '{}'".format(self.address)

    def add_consumer(self, link):
        assert link.is_sender
        assert link not in self.consumers

        _plano.notice("Adding consumer for '{}' to {}", link.connection.remote_container, self)

        self.consumers.append(link)

    def remove_consumer(self, link):
        assert link.is_sender

        _plano.notice("Removing consumer for '{}' from {}", link.connection.remote_container, self)

        try:
            self.consumers.remove(link)
        except ValueError:
            pass

    def store_message(self, message):
        self.messages.append(message)

    def forward_messages(self, link):
        assert link.is_sender

        while link.credit > 0:
            try:
                message = self.messages.popleft()
            except IndexError:
                break

            link.send(message)
