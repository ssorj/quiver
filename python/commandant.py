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
import inspect as _inspect
import os as _os
import runpy as _runpy
import sys as _sys
import tempfile as _tempfile

class Command(object):
    def __init__(self, home, name=None):
        self.home = home
        self.name = name

        self._parser = _argparse.ArgumentParser()
        self._parser.formatter_class = _argparse.RawDescriptionHelpFormatter

        self._args = None

        self.add_argument("--quiet", action="store_true",
                          help="Print no logging to the console")
        self.add_argument("--verbose", action="store_true",
                          help="Print detailed logging to the console")
        self.add_argument("--init-only", action="store_true",
                          help=_argparse.SUPPRESS)

        if self.name is None:
            self.name = self._parser.prog

        self.id = self.name

    def add_argument(self, *args, **kwargs):
        self.parser.add_argument(*args, **kwargs)

    def add_subparsers(self, *args, **kwargs):
        return self.parser.add_subparsers(*args, **kwargs)

    @property
    def parser(self):
        return self._parser

    @property
    def args(self):
        return self._args

    @property
    def description(self):
        return self.parser.description

    @description.setter
    def description(self, text):
        self.parser.description = text.strip()

    @property
    def epilog(self):
        return self.parser.epilog

    @epilog.setter
    def epilog(self, text):
        self.parser.epilog = text.strip()

    def load_config(self):
        dir_ = _os.path.expanduser("~")
        config_file = _os.path.join(dir_, ".config", self.name, "config.py")
        config = dict()

        if _os.path.exists(config_file):
            entries = _runpy.run_path(config_file, config)
            config.update(entries)

        return config

    def init(self):
        assert self._args is None

        self._args = self.parser.parse_args()

        self.quiet = self.args.quiet
        self.verbose = self.args.verbose
        self.init_only = self.args.init_only

    def run(self):
        raise NotImplementedError()

    def main(self):
        try:
            self.init()

            assert self._args is not None

            if self.init_only:
                return

            self.run()
        except KeyboardInterrupt:
            pass

    def info(self, message, *args):
        if self.verbose:
            self.print_message(message, *args)

    def notice(self, message, *args):
        if not self.quiet:
            self.print_message(message, *args)

    def warn(self, message, *args):
        message = "Warning! {}".format(message)
        self.print_message(message, *args)

    def error(self, message, *args):
        message = "Error! {}".format(message)
        self.print_message(message, *args)

    def fail(self, message, *args):
        self.error(message, *args)
        _sys.exit(1)

    def print_message(self, message, *args):
        message = message[0].upper() + message[1:]
        message = message.format(*args)
        message = "{}: {}".format(self.id, message)

        _sys.stderr.write("{}\n".format(message))
        _sys.stderr.flush()

class TestCommand(Command):
    def __init__(self, home, test_modules, name=None):
        super(TestCommand, self).__init__(home, name=name)

        self.test_modules = []

        for module in test_modules:
            _TestModule(self, module)

        self.test_prefixes = ["test_"]

    def init(self):
        super(TestCommand, self).init()

        for module in self.test_modules:
            module.init()

    def run(self):
        for module in self.test_modules:
            module.run_tests()

class _TestModule(object):
    def __init__(self, command, module):
        self.command = command
        self.module = module

        self.init_function = None
        self.test_functions = []
        self.test_functions_by_name = {}

        self.command.test_modules.append(self)

    def init(self):
        self.init_function = getattr(self.module, "init_test_module")

        if self.init_function is not None:
            assert _inspect.isroutine(self.init_function), self.init_function

        members = _inspect.getmembers(self.module, _inspect.isroutine)

        for name, function in members:
            for prefix in self.command.test_prefixes:
                if name.startswith(prefix):
                    break
            else:
                continue

            self.test_functions.append(function)
            self.test_functions_by_name[name] = function

    def run_tests(self):
        if self.init_function is not None:
            self.init_function()

        failures = 0

        if not self.command.verbose:
            self._print("## Test module '{}'".format(self.module.__name__))

        for function in self.test_functions:
            failures += self._run_test(function)

        if failures == 0:
            print("All tests passed")
        else:

            _sys.exit("Some tests failed")

    def _run_test(self, function, *args, **kwargs):
        long_name = "{}:{}".format(self.module.__name__, function.__name__)
        short_name = function.__name__

        if self.command.verbose:
            self.command.notice("Running test '{}'", long_name)

            try:
                function(*args, **kwargs)
            except:
                self.command.error("Test '{}' FAILED", long_name)
                return 1

            self.command.notice("Test '{}' PASSED", long_name)
        else:
            self._print("{:.<73} ".format(short_name + " "), end="")

            output_file = _tempfile.mktemp(prefix="commandant-")

            try:
                with open(output_file, "w") as out:
                    with _OutputRedirected(out, out):
                        function(*args, **kwargs)
            except:
                self._print("FAILED")

                with open(output_file, "r") as out:
                    for line in out:
                        _sys.stderr.write("> ")
                        _sys.stderr.write(line)

                _sys.stderr.flush()

                return 1
            finally:
                _os.remove(output_file)

            self._print("PASSED")

        return 0

    def _print(self, *args, **kwargs):
        if self.command.quiet:
            return

        print(*args, **kwargs)
        _sys.stdout.flush()
        _sys.stderr.flush()

class _OutputRedirected(object):
    def __init__(self, stdout=None, stderr=None):
        self.new_stdout = stdout or _sys.stdout
        self.new_stderr = stderr or _sys.stderr

        self.old_stdout = _sys.stdout
        self.old_stderr = _sys.stderr

    def __enter__(self):
        self.flush()

        _sys.stdout = self.new_stdout
        _sys.stderr = self.new_stderr

    def __exit__(self, exc_type, exc_value, traceback):
        self.flush()

        _sys.stdout = self.old_stdout
        _sys.stderr = self.old_stderr

    def flush(self):
        _sys.stdout.flush()
        _sys.stderr.flush()
