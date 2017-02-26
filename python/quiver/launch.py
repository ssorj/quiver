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

import os as _os
import plano as _plano
import shlex as _shlex
import subprocess as _subprocess
import sys as _sys
import time as _time

from .common import *
from .common import _install_sigterm_handler

_description = "XXX"
_epilog = "XXX"

class QuiverLaunchCommand(Command):
    def __init__(self, home_dir):
        super(QuiverLaunchCommand, self).__init__(home_dir)

        self.parser.description = _description.lstrip()
        self.parser.epilog = _epilog.lstrip()
        
        self.parser.add_argument("url", metavar="URL",
                                 help="The location of a message queue")
        self.parser.add_argument("--sender-count", metavar="COUNT", default=1, type=int)
        self.parser.add_argument("--sender-impl", metavar="IMPL", default="qpid-proton-python")
        self.parser.add_argument("--sender-options", metavar="OPTIONS", default="")
        self.parser.add_argument("--receiver-count", metavar="COUNT", default=1, type=int)
        self.parser.add_argument("--receiver-impl", metavar="IMPL", default="qpid-proton-python")
        self.parser.add_argument("--receiver-options", metavar="OPTIONS", default="")

        self.add_common_tool_arguments()
        
    def init(self):
        super(QuiverLaunchCommand, self).init()
        
        _plano.set_message_output(_sys.stdout)
        
        self.sender_count = self.args.sender_count
        self.sender_impl = self.args.sender_impl
        self.sender_options = _shlex.split(self.args.sender_options)

        self.receiver_count = self.args.receiver_count
        self.receiver_impl = self.args.receiver_impl
        self.receiver_options = _shlex.split(self.args.receiver_options)

        self.init_url_attributes()
        self.init_common_tool_attributes()

    def run(self):
        exit_code = 0

        sender_command = ["quiver-arrow", "send", self.url, "--impl", self.sender_impl]
        sender_command += self.sender_options

        receiver_command = ["quiver-arrow", "receive", self.url, "--impl", self.receiver_impl]
        receiver_command += self.receiver_options

        senders = list()
        receivers = list()

        for i in range(self.receiver_count):
            receiver = _plano.start_process(receiver_command)
            receivers.append(receiver)

        _plano.wait_for_port(self.port)

        for i in range(args.senders):
            sender = _plano.start_process(sender_command)
            senders.append(sender)

        try:
            try:
                for sender in senders:
                    _plano.wait_for_process(sender)

                for receiver in receivers:
                    _plano.wait_for_process(receiver)
            except:
                for sender in senders:
                    _plano.stop_process(sender)

                for receiver in receivers:
                    _plano.stop_process(receiver)

                raise

            for sender in senders:
                if sender.returncode != 0:
                    exit_code = 1
                    break

            for receiver in receivers:
                if receiver.returncode != 0:
                    exit_code = 1
                    break
        except KeyboardInterrupt:
            pass
        except:
            _traceback.print_exc()
            exit_code = 1
        finally:
            _plano.exit(exit_code)
