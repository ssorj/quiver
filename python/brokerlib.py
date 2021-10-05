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

class Broker:
    def __init__(self, host, port, id=None, ready_file=None,
                 user=None, password=None,
                 cert=None, key=None, trust_store=None,
                 quiet=False, verbose=False, init_only=False):
        self.host = host
        self.port = port
        self.id = id
        self.user = user
        self.password = password
        self.ready_file = ready_file
        self.cert = cert
        self.key = key
        self.trust_store = trust_store
        self.quiet = quiet
        self.verbose = verbose
        self.init_only = init_only

        if self.id is None:
            self.id = "broker-{0}".format(str(_uuid.uuid4())[:8])

        self.container = _reactor.Container(_Handler(self))
        self.container.container_id = self.id # XXX Obnoxious

        self._config_dir = None

    def init(self):
        self.info("Initializing {0}", self)

        if self.user is not None:
            if self.password is None:
                self.fail("A password is required for user authentication")

            self._init_sasl_config()

        if self.cert is not None:
            if self.key is None:
                self.fail("Both the cert and key files must be provided")

            if not _os.path.isfile(self.key):
                self.fail("Private key file {0} does not exist", self.key)

            if not _os.path.isfile(self.cert):
                self.fail("Certificate file {0} does not exist", self.cert)

            if self.trust_store and not _os.path.isfile(self.trust_store):
                self.fail("Trust store file {0} does not exist", self.trust_store)

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

    def debug(self, message, *args):
        pass

    def info(self, message, *args):
        pass

    def notice(self, message, *args):
        pass

    def warn(self, message, *args):
        pass

    def error(self, message, *args):
        self.log(message, *args)

    def fail(self, message, *args):
        self.error(message, *args)
        _sys.exit(1)

    def log(self, message, *args):
        message = message[0].upper() + message[1:]
        message = message.format(*args)
        message = "{0}: {1}".format(self.id, message)

        _sys.stderr.write("{0}\n".format(message))
        _sys.stderr.flush()

    def run(self):
        try:
            if self.init_only:
                return

            self.container.run()
        finally:
            if self._config_dir and _os.path.exists(self._config_dir):
                _shutil.rmtree(self.dir, ignore_errors=True)

class _Queue:
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

        self.broker.info("Added consumer for {0} to {1}", _container_repr(link.connection), self)

    def remove_consumer(self, link):
        assert link.is_sender

        try:
            self.consumers.remove(link)
        except ValueError:
            return

        self.broker.info("Removed consumer for {0} from {1}", _container_repr(link.connection), self)

    def store_message(self, delivery, message):
        self.messages.append(message)

        self.broker.notice("Stored {0} from {1} on {2}", message, _container_repr(delivery.connection), self)

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

                self.broker.notice("Forwarded {0} on {1} to {2}", message, self, _container_repr(consumer.connection))

        self.consumers.rotate(sent)

class _Handler(_handlers.MessagingHandler):
    def __init__(self, broker):
        super(_Handler, self).__init__()

        self.broker = broker
        self.queues = dict()
        self.verbose = False

    def on_start(self, event):
        interface = "{0}:{1}".format(self.broker.host, self.broker.port)

        if self.broker.cert is not None:
            server_ssl_domain = event.container.ssl.server
            server_ssl_domain.set_credentials(self.broker.cert, self.broker.key, None)

            if self.broker.trust_store:
                server_ssl_domain.set_trusted_ca_db(self.broker.trust_store)
                server_ssl_domain.set_peer_authentication(_proton.SSLDomain.VERIFY_PEER_NAME,
                                                          self.broker.trust_store)
            else:
                server_ssl_domain.set_peer_authentication(_proton.SSLDomain.ANONYMOUS_PEER)

        self.acceptor = event.container.listen(interface)

        self.broker.notice("Listening for connections on '{0}'", interface)

        if self.broker.ready_file is not None:
            with open(self.broker.ready_file, "w") as f:
                f.write("ready\n")

    def get_queue(self, address):
        try:
            queue = self.queues[address]
        except KeyError:
            queue = self.create_queue(address)

        return queue

    def create_queue(self, address):
        assert address not in self.queues, address

        queue = _Queue(self.broker, address)
        self.queues[address] = queue
        return queue

    def on_link_opening(self, event):
        if event.link.is_sender:
            # A client receiving from the broker

            if event.link.remote_source.dynamic:
                # A temporary queue
                address = "{0}/{1}".format(event.connection.remote_container, event.link.name)
                queue = self.create_queue(address)
            elif event.link.remote_source.address in (None, ""):
                raise Exception("The client created a receiver with no source address")
            else:
                # A named queue
                address = event.link.remote_source.address
                queue = self.get_queue(address)

            assert address is not None

            event.link.source.address = address
            queue.add_consumer(event.link)

        if event.link.is_receiver:
            # A client sending to the broker

            if event.link.remote_target.dynamic:
                # A temporary queue
                address = "{0}/{1}".format(event.connection.remote_container, event.link.name)
                queue = self.create_queue(address)
            elif event.link.remote_target.address in (None, ""):
                # Anonymous relay - no queueing
                address = None
            else:
                # A named queue
                address = event.link.remote_target.address
                queue = self.get_queue(address)

            event.link.target.address = address

    def on_link_closing(self, event):
        if event.link.is_sender:
            queue = self.queues[event.link.source.address]
            queue.remove_consumer(event.link)

    def on_connection_opening(self, event):
        # XXX I think this should happen automatically
        event.connection.container = event.container.container_id

    def on_connection_opened(self, event):
        self.broker.notice("Opened connection from {0}", _container_repr(event.connection))

    def on_connection_closing(self, event):
        self.remove_consumers(event.connection)

    def on_connection_closed(self, event):
        self.broker.notice("Closed connection from {0}", _container_repr(event.connection))

    def on_disconnected(self, event):
        self.broker.notice("Disconnected from {0}", _container_repr(event.connection))

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
        template = "Container '{0}' {1} {2} for {3}"
        container = event.connection.remote_container
        source = _terminus_repr(event.link.source)
        delivery = event.delivery

        if delivery.remote_state == delivery.ACCEPTED:
            self.broker.info(template, container, "accepted", _delivery_repr(delivery), source)
        elif delivery.remote_state == delivery.REJECTED:
            self.broker.warn(template, container, "rejected", _delivery_repr(delivery), source)
        elif delivery.remote_state == delivery.RELEASED:
            self.broker.notice(template, container, "released", _delivery_repr(delivery), source)
        elif delivery.remote_state == delivery.MODIFIED:
            self.broker.notice(template, container, "modified", _delivery_repr(delivery), source)

    def on_message(self, event):
        message = event.message
        delivery = event.delivery
        address = event.link.target.address

        if address in (None, ""):
            address = message.address

        queue = self.get_queue(address)
        queue.store_message(delivery, message)
        queue.forward_messages()

    def on_unhandled(self, name, event):
        self.broker.debug("Unhandled event: {0} {1}", name, event)

def _container_repr(connection):
    return "container '{0}'".format(connection.remote_container)

def _terminus_repr(terminus):
    return "terminus '{0}'".format(terminus.address)

def _delivery_repr(delivery):
    return "delivery '{0}'".format(delivery.tag)

def wait_for_broker(ready_file, timeout=30):
    start_time = _time.time()
    interval = 0.125

    while True:
        if _time.time() - start_time > timeout:
            raise Exception("Timed out waiting for the broker")

        _time.sleep(interval)

        with open(ready_file, "r") as f:
            if f.read() == "ready\n":
                break

        if interval < 1:
            interval = interval * 2
        else:
            print("Still waiting for the broker")

def main():
    import argparse

    parser = argparse.ArgumentParser(description="An AMQP message broker for testing")

    parser.add_argument("--host", metavar="HOST", default="localhost",
                        help="Listen for connections on HOST (default localhost)")
    parser.add_argument("--port", metavar="PORT", default=5672, type=int,
                        help="Listen for connections on PORT (default 5672)")
    parser.add_argument("--id", metavar="ID",
                        help="Set the container identity to ID (default is generated)")
    parser.add_argument("--ready-file", metavar="FILE",
                        help="The file used to indicate the server is ready")
    # parser.add_argument("--user", metavar="USER",
    #                   help="Require USER")
    # parser.add_argument("--password", metavar="SECRET",
    #                   help="Require SECRET")
    parser.add_argument("--cert", metavar="FILE",
                        help="The TLS certificate file")
    parser.add_argument("--key", metavar="FILE",
                        help="The TLS private key file")
    parser.add_argument("--trust-store", metavar="FILE",
                        help="The file containing trusted client certificates.  "
                        "If set, the server verifies client identities.")
    parser.add_argument("--quiet", action="store_true",
                        help="Print no logging to the console")
    parser.add_argument("--verbose", action="store_true",
                        help="Print detailed logging to the console")
    parser.add_argument("--init-only", action="store_true",
                      help=argparse.SUPPRESS)

    args = parser.parse_args()

    class _Broker(Broker):
        def debug(self, message, *args):
            if self.verbose:
                self.log(message, *args)

        def info(self, message, *args):
            if self.verbose:
                self.log(message, *args)

        def notice(self, message, *args):
            if not self.quiet:
                self.log(message, *args)

        def warn(self, message, *args):
            message = "Warning! {0}".format(message)
            self.log(message, *args)

        def error(self, message, *args):
            message = "Error! {0}".format(message)
            self.log(message, *args)

    broker = _Broker(args.host, args.port, id=args.id, ready_file=args.ready_file,
                     # user=args.user, password=args.password,
                     cert=args.cert, key=args.key, trust_store=args.trust_store,
                     quiet=args.quiet, verbose=args.verbose, init_only=args.init_only)

    try:
        broker.run()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
