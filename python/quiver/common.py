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

import argparse as _argparse
import json as _json
import numpy as _numpy
import os as _os
import plano as _plano
import resource as _resource
import shlex as _shlex
import signal as _signal
import subprocess as _subprocess
import sys as _sys
import tempfile as _tempfile
import time as _time

try:
    from urllib.parse import urlparse as _urlparse
except ImportError:
    from urlparse import urlparse as _urlparse

ARROW_IMPLS = [
    "activemq-artemis-jms",
    "activemq-jms",
    "qpid-jms",
    "qpid-messaging-cpp",
    "qpid-messaging-python",
    "qpid-proton-cpp",
    "qpid-proton-python",
    "rhea",
    "vertx-proton",
]

PEER_TO_PEER_ARROW_IMPLS = [
    "qpid-proton-cpp",
    "qpid-proton-python",
    "rhea",
]

SERVER_IMPLS = [
    "activemq",
    "activemq-artemis",
    "builtin",
    "qpid-cpp",
    "qpid-dispatch",
]

_arrow_impl_aliases = {
    "artemis-jms": "activemq-artemis-jms",
    "cpp": "qpid-proton-cpp",
    "java": "vertx-proton",
    "javascript": "rhea",
    "jms": "qpid-jms",
    "python": "qpid-proton-python",
}

_server_impl_aliases = {
    "artemis": "activemq-artemis",
    "dispatch": "qpid-dispatch",
    "qdrouterd": "qpid-dispatch",
    "qpidd": "qpid-cpp",
}

class CommandError(Exception):
    def __init__(self, message, *args):
        if isinstance(message, Exception):
            message = str(message)

        message = message.format(*args)

        super(CommandError, self).__init__(message)

class Command(object):
    def __init__(self, home_dir):
        self.home_dir = home_dir

        self.parser = _argparse.ArgumentParser()
        self.parser.formatter_class = _Formatter

        self.init_only = False
        self.quiet = False
        self.verbose = False

        self.args = None

    def init(self):
        assert self.parser is not None
        assert self.args is None

        self.args = self.parser.parse_args()

        _plano.set_message_threshold("warn")

        if self.quiet:
            _plano.set_message_threshold("error")

        if self.verbose:
            _plano.set_message_threshold("notice")

    def add_common_test_arguments(self):
        self.parser.add_argument("-m", "--messages", metavar="COUNT",
                                 help="Send or receive COUNT messages",
                                 default="1m")
        self.parser.add_argument("--body-size", metavar="COUNT",
                                 help="Send message bodies containing COUNT bytes",
                                 default="100")
        self.parser.add_argument("--credit", metavar="COUNT",
                                 help="Sustain credit for COUNT incoming messages",
                                 default="1000")
        self.parser.add_argument("--timeout", metavar="SECONDS",
                                 help="Fail after SECONDS without transfers",
                                 default="10")

    def add_common_tool_arguments(self):
        self.parser.add_argument("--init-only", action="store_true",
                                 help="Initialize and immediately exit")
        self.parser.add_argument("--quiet", action="store_true",
                                 help="Print nothing to the console")
        self.parser.add_argument("--verbose", action="store_true",
                                 help="Print details to the console")

    def init_common_test_attributes(self):
        self.messages = self.parse_int_with_unit(self.args.messages)
        self.body_size = self.parse_int_with_unit(self.args.body_size)
        self.credit_window = self.parse_int_with_unit(self.args.credit)
        self.timeout = self.parse_int_with_unit(self.args.timeout)

    def init_common_tool_attributes(self):
        self.init_only = self.args.init_only
        self.quiet = self.args.quiet
        self.verbose = self.args.verbose

    def init_url_attributes(self):
        self.url = self.args.url

        url = _urlparse(self.url)

        if url.path is None:
            raise CommandError("The URL has no path")

        self.host = url.hostname
        self.port = url.port
        self.path = url.path

        if self.host is None:
            self.host = "localhost"

        if self.port is None:
            self.port = "-"

        self.port = str(self.port)

        if self.path.startswith("/"):
            self.path = self.path[1:]

    def init_output_dir(self):
        self.output_dir = self.args.output

        if self.output_dir is None:
            self.output_dir = _tempfile.mkdtemp(prefix="quiver-")

        _plano.make_dir(self.output_dir)

    def parse_int_with_unit(self, value):
        assert self.parser is not None

        try:
            if value.endswith("m"): return int(value[:-1]) * 1000 * 1000
            if value.endswith("k"): return int(value[:-1]) * 1000
            return int(value)
        except ValueError:
            self.parser.error("Failure parsing '{}' as integer with unit".format(value))

    def run(self):
        raise NotImplementedError()

    def main(self):
        try:
            self.init()

            if self.init_only:
                return

            self.run()
        except CommandError as e:
            _plano.exit(str(e))
        except KeyboardInterrupt:
            pass

    def get_arrow_impl_name(self, name, fallback=None):
        if name in ARROW_IMPLS:
            return name

        if name in _arrow_impl_aliases:
            return _arrow_impl_aliases[name]

        return fallback

    def get_server_impl_name(self, name, fallback=None):
        if name in SERVER_IMPLS:
            return name

        if name in _server_impl_aliases:
            return _server_impl_aliases[name]

        return fallback

    def get_arrow_impl_file(self, name):
        return _plano.join(self.home_dir, "exec", "quiver-arrow-{}".format(name))

    def get_server_impl_file(self, name):
        return _plano.join(self.home_dir, "exec", "quiver-server-{}".format(name))

class _Formatter(_argparse.ArgumentDefaultsHelpFormatter,
                 _argparse.RawDescriptionHelpFormatter):
    pass

def now():
    return long(_time.time() * 1000)
