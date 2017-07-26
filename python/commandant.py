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
import fnmatch as _fnmatch
import inspect as _inspect
import os as _os
import runpy as _runpy
import sys as _sys
import tempfile as _tempfile
import time as _time

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

_test_epilog = """
patterns:
  The --include and --exclude options take comma-separated lists of
  shell-style match expressions.  '*' matches multiple characters, and
  '?' matches exactly one character.  Take care to escape these so
  that your shell doesn't expand them.
"""

class TestCommand(Command):
    def __init__(self, home, test_modules, name=None):
        super(TestCommand, self).__init__(home, name=name)

        self.test_modules = []

        for module in test_modules:
            _TestModule(self, module)

        self.epilog = _test_epilog

        self.test_prefixes = ["test_"]

        self.add_argument("--list", action="store_true",
                          help="Print the test names and exit")
        self.add_argument("--include", metavar="PATTERNS",
                          help="Run only tests with names matching PATTERNS (default '*')",
                          default="*")
        self.add_argument("--exclude", metavar="PATTERNS",
                          help="Do not run tests with names matching PATTERNS")
        self.add_argument("--iterations", metavar="COUNT", type=int, default=1,
                          help="Run the tests COUNT times (default 1)")

    def init(self):
        super(TestCommand, self).init()

        self.list_only = self.args.list
        self.include_patterns = self.args.include.split(",")
        self.exclude_patterns = []
        self.iterations = self.args.iterations

        if self.args.exclude is not None:
            self.exclude_patterns = self.args.exclude.split(",")

        for module in self.test_modules:
            module.init()

    def run(self):
        sessions = list()

        for i in range(self.iterations):
            for module in self.test_modules:
                session = _TestSession(self)
                sessions.append(session)

                module.run_tests(session)

        for session in sessions:
            if len(session.failed_tests) != 0:
                break
        else:
            print("RESULT: All tests passed")
            return

        print("RESULT: Some tests failed")

class _TestSession(object):
    def __init__(self, module):
        self.module = module

        self.passed_tests = []
        self.failed_tests = []

class _TestFunction(object):
    def __init__(self, module, function):
        self.module = module
        self.function = function

        self.module.test_functions.append(self)
        self.module.test_functions_by_name[self.name] = self

    def __call__(self, session):
        return self.function(session)

    def __repr__(self):
        return "test '{}:{}'".format(self.module.name, self.name)

    @property
    def name(self):
        return self.function.__name__

class _TestModule(object):
    def __init__(self, command, module):
        self.command = command
        self.module = module

        self.open_function = None
        self.close_function = None

        self.test_functions = []
        self.test_functions_by_name = {}

        self.command.test_modules.append(self)

    def __repr__(self):
        return "module '{}'".format(self.name)

    @property
    def name(self):
        return self.module.__name__

    def init(self):
        self.open_function = getattr(self.module, "open_test_session", None)
        self.close_function = getattr(self.module, "close_test_session", None)

        if self.open_function is not None:
            assert _inspect.isroutine(self.open_function), self.open_function

        if self.close_function is not None:
            assert _inspect.isroutine(self.close_function), self.close_function

        members = _inspect.getmembers(self.module, _inspect.isroutine)

        def is_test_function(name):
            for prefix in self.command.test_prefixes:
                if name.startswith(prefix):
                    return True

        def included(name):
            for pattern in self.command.include_patterns:
                if _fnmatch.fnmatchcase(name, pattern):
                    return True

        def excluded(name):
            for pattern in self.command.exclude_patterns:
                if _fnmatch.fnmatchcase(name, pattern):
                    return True

        for name, function in members:
            if not is_test_function(name):
                continue

            if not included(name):
                self.command.info("Skipping test '{}:{}' (not included)", self.module.__name__, name)
                continue

            if excluded(name):
                self.command.info("Skipping test '{}:{}' (excluded)", self.module.__name__, name)
                continue

            _TestFunction(self, function)

    def run_tests(self, session):
        if self.command.list_only:
            for function in self.test_functions:
                print(function)

            return

        if not self.command.verbose:
            self.command.notice("Running tests from {}", self)

        if self.open_function is not None:
            self.open_function(session)

        try:
            for function in self.test_functions:
                self.run_test(session, function)
        finally:
            if self.close_function is not None:
                self.close_function(session)

    def run_test(self, session, function):
        start_time = _time.time()

        if self.command.verbose:
            self.command.notice("Running {}", function)

            try:
                function(session)
            except KeyboardInterrupt:
                raise
            except:
                session.failed_tests.append(function)
                self.command.error("{} FAILED ({})", function, _elapsed_time(start_time))

                return

            session.passed_tests.append(function)
            self.command.notice("{} PASSED ({})", function, _elapsed_time(start_time))
        else:
            self._print("{:.<73} ".format(function.name + " "), end="")

            output_file = _tempfile.mkstemp(prefix="commandant-")[1]

            try:
                with open(output_file, "w") as out:
                    with _OutputRedirected(out, out):
                        function(session)
            except KeyboardInterrupt:
                raise
            except:
                session.failed_tests.append(function)
                self._print("FAILED {:>6}".format(_elapsed_time(start_time)))

                with open(output_file, "r") as out:
                    for line in out:
                        _sys.stderr.write("> ")
                        _sys.stderr.write(line)

                _sys.stderr.flush()

                return
            finally:
                _os.remove(output_file)

            session.passed_tests.append(function)
            self._print("PASSED {:>6}".format(_elapsed_time(start_time)))

    def _print(self, *args, **kwargs):
        if self.command.quiet:
            return

        print(*args, **kwargs)
        _sys.stdout.flush()
        _sys.stderr.flush()

def _elapsed_time(start_time):
    elapsed = _time.time() - start_time

    if elapsed > 240:
        return "{:.0f}m".format(elapsed / 60)

    if elapsed > 60:
        return "{:.0f}s".format(elapsed)

    return "{:.1f}s".format(elapsed)

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
