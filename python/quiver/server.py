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
from .common import __version__, _epilog_address_urls, _epilog_server_impls

_description = """
Start a message server with the given queue.
"""

_epilog = """
{_epilog_address_urls}

{_epilog_server_impls}
""".format(**globals())

class QuiverServerCommand(Command):
    def __init__(self, home_dir):
        super(QuiverServerCommand, self).__init__(home_dir)

        self.parser.description = _description.lstrip()
        self.parser.epilog = _epilog.lstrip()

        self.parser.add_argument("url", metavar="ADDRESS-URL",
                                 help="The location of a message source or target")
        self.parser.add_argument("--impl", metavar="NAME",
                                 help="Use NAME implementation",
                                 default=DEFAULT_SERVER_IMPL)
        self.parser.add_argument("--info", action="store_true",
                                 help="Print implementation details and exit")
        self.parser.add_argument("--impl-info", action="store_true", dest="info",
                                 help=_argparse.SUPPRESS)
        self.parser.add_argument("--ready-file", metavar="FILE",
                                 help="The file used to indicate the server is ready")
        self.parser.add_argument("--prelude", metavar="PRELUDE", default="",
                                 help="Commands to precede the implementation invocation")
        self.parser.add_argument("--cert", metavar="CERT.PEM",
                                 help="Certificate filename")
        self.parser.add_argument("--key", metavar="PRIVATE-KEY.PEM",
                                 help="Private key filename")
        self.parser.add_argument("--key-password", metavar="key_password",
                                 help="Certificate password (required for encrypted private keys)")
        self.parser.add_argument("--trusted-db", metavar="TRUSTED-DB.PEM",
                                 help="Database of trusted CA certificate(s).  If specified the peer's client is tested"
                                      "against this source of trust.")
        self.parser.add_argument("--sasl-user", metavar="SASL USERNAME",
                                 help="SASL username that the peer must present")
        self.parser.add_argument("--sasl-password", metavar="SASL PASSWORD",
                                 help="SASL password that the peer must present. Ignored is --sasl-user is not present.")

        self.add_common_tool_arguments()

    def init(self):
        self.intercept_info_request(DEFAULT_SERVER_IMPL)

        super(QuiverServerCommand, self).init()

        self.impl = require_impl(self.args.impl)
        self.ready_file = self.args.ready_file
        self.prelude = _shlex.split(self.args.prelude)
        self.cert = self.args.cert
        self.key = self.args.key
        self.key_password = self.args.key_password
        self.trusted_db = self.args.trusted_db
        self.sasl_user = self.args.sasl_user
        self.sasl_password = self.args.sasl_password

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

        if self.scheme:
            args.append("scheme={}".format(self.scheme))

        if self.cert:
            args.append("cert={}".format(self.cert))

        if self.key:
            args.append("key={}".format(self.key))

        if self.key_password:
            args.append("key-password={}".format(self.key_password))

        if self.trusted_db:
            args.append("trusted-db={}".format(self.trusted_db))

        if self.sasl_user:
            args.append("user={}".format(self.sasl_user))

        if self.sasl_password:
            args.append("password={}".format(self.sasl_password))

        _plano.call(args)

class BuiltinBroker(_brokerlib.Broker):
    def __init__(self, scheme, host, port, path, ready_file,
                 cert=None,
                 key=None,
                 key_password=None,
                 trusted_db=None,
                 user=None,
                 password=None):
        if ready_file == "-":
            ready_file = None

        super().__init__(scheme, host, port, id="quiver-server-builtin", ready_file=ready_file,
                         cert=cert, key=key, key_password=key_password, trusted_db=trusted_db,
                         user=user, password=password)

        self.path = path

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
