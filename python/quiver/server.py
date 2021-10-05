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

import argparse as _argparse
import brokerlib as _brokerlib
import collections as _collections
import plano as _plano
import proton as _proton
import proton.handlers as _handlers
import proton.reactor as _reactor
import shlex as _shlex
import subprocess as _subprocess
import uuid as _uuid

from .common import *
from .common import __version__, _epilog_urls, _epilog_server_impls

_description = """
Start a message server with the given queue.
"""

_epilog = """
{_epilog_urls}

{_epilog_server_impls}
""".format(**globals())

class QuiverServerCommand(Command):
    def __init__(self, home_dir):
        super(QuiverServerCommand, self).__init__(home_dir)

        self.parser.description = _description.lstrip()
        self.parser.epilog = _epilog.lstrip()

        self.parser.add_argument("url", metavar="URL",
                                 help="The location of a message source or target")
        self.parser.add_argument("--impl", metavar="IMPL",
                                 help="Use the IMPL server implementation",
                                 default=DEFAULT_SERVER_IMPL)
        self.parser.add_argument("--info", action="store_true",
                                 help="Print implementation details and exit")
        self.parser.add_argument("--ready-file", metavar="FILE",
                                 help="The file used to indicate the server is ready")
        self.parser.add_argument("--prelude", metavar="PRELUDE", default="",
                                 help="Commands to precede the implementation invocation")
        self.parser.add_argument("--user", metavar="USER",
                                 help="The SASL username that the client must present")
        self.parser.add_argument("--password", metavar="SECRET",
                                 help="SASL password that the client must present.  "
                                 "Ignored if --sasl-user is not present.")
        self.parser.add_argument("--cert", metavar="FILE",
                                 help="The TLS certificate file")
        self.parser.add_argument("--key", metavar="FILE",
                                 help="The TLS private key file")
        self.parser.add_argument("--trust-store", metavar="FILE",
                                 help="The file containing trusted client certificates.  "
                                 "If set, the server verifies client identities.")

        self.add_common_tool_arguments()

    def init(self):
        self.intercept_info_request(DEFAULT_SERVER_IMPL)

        super(QuiverServerCommand, self).init()

        self.impl = require_impl(self.args.impl)
        self.ready_file = self.args.ready_file
        self.prelude = _shlex.split(self.args.prelude)
        self.user = self.args.user
        self.password = self.args.password
        self.cert = self.args.cert
        self.key = self.args.key
        self.trust_store = self.args.trust_store

        if self.ready_file is None:
            self.ready_file = "-"

        self.init_url_attributes()
        self.init_common_tool_attributes()

    def run(self):
        args = self.prelude + [
            self.impl.file,
            "host={}".format(self.host),
            "port={}".format(self.port),
            "path={}".format(self.path),
            "ready-file={}".format(self.ready_file),
        ]

        if self.user:
            args.append("user={}".format(self.user))

        if self.password:
            args.append("password={}".format(self.password))

        if self.cert:
            args.append("cert={}".format(self.cert))

        if self.key:
            args.append("key={}".format(self.key))

        if self.trust_store:
            args.append("trust-store={}".format(self.trust_store))

        if self.quiet:
            args.append("quiet=1")

        if self.verbose:
            args.append("verbose=1")

        _plano.call(args)

class BuiltinBroker(_brokerlib.Broker):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.id = "quiver-server-builtin"

        if self.ready_file == "-":
            self.ready_file = None

    def init(self):
        if self.quiet:
            _plano.enable_logging("error")

        if self.verbose:
            _plano.enable_logging("notice")

        super().init()

    def info(self, message, *args):
        _plano.notice(message, *args)

    def notice(self, message, *args):
        _plano.notice(message, *args)

    def warn(self, message, *args):
        _plano.warn(message, *args)

    def error(self, message, *args):
        _plano.error(message, *args)

    def fail(self, message, *args):
        _plano.fail(message, *args)
