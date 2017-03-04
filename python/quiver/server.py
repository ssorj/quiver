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

import plano as _plano
import shlex as _shlex
import subprocess as _subprocess

from .common import *
from .common import _install_sigterm_handler

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

        proc = _subprocess.Popen(args)

        _install_sigterm_handler(proc)

        _plano.notice("Process {} (server) started", proc.pid)

        while proc.poll() is None:
            _plano.sleep(1)

        if proc.returncode == 0:
            _plano.notice("Process {} (server) exited normally", proc.pid)
        else:
            raise CommandError("Process {} (server) exited with code {}", proc.pid, proc.returncode)
