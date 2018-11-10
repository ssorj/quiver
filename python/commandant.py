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
import signal as _signal
import subprocess as _subprocess
import sys as _sys
import tempfile as _tempfile
import time as _time
import traceback as _traceback

class Command(object):
    def __init__(self, home=None, name=None, standard_args=True):
        self.home = home
        self.name = name

        self._parser = _argparse.ArgumentParser()
        self._parser.formatter_class = _argparse.RawDescriptionHelpFormatter

        self._args = None

        if standard_args:
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
        message = "Warning! {0}".format(message)
        self.print_message(message, *args)

    def error(self, message, *args):
        message = "Error! {0}".format(message)
        self.print_message(message, *args)

    def fail(self, message, *args):
        self.error(message, *args)
        _sys.exit(1)

    def print_message(self, message, *args):
        message = message[0].upper() + message[1:]
        message = message.format(*args)
        message = "{0}: {1}".format(self.id, message)

        _sys.stderr.write("{0}\n".format(message))
        _sys.stderr.flush()

class TestTimedOut(Exception):
    pass

class TestSkipped(Exception):
    pass

class TestCommand(Command):
    def __init__(self, test_modules, home=None, name=None):
        super(TestCommand, self).__init__(home=home, name=name)

        self.test_modules = list()

        for module in test_modules:
            _TestModule(self, module)

        self.test_prefixes = ["test_"]

        self.add_argument("-l", "--list", action="store_true",
                          help="Print the test names and exit")
        self.add_argument("include", metavar="PATTERN", nargs="*",
                          help="Run only tests with names matching PATTERN. " \
                          "This option can be repeated.")
        self.add_argument("-e", "--exclude", metavar="PATTERN", action="append", default=list(),
                          help="Do not run tests with names matching PATTERN. " \
                          "This option can be repeated.")
        self.add_argument("--iterations", metavar="COUNT", type=int, default=1,
                          help="Run the tests COUNT times (default 1)")
        self.add_argument("--timeout", metavar="SECONDS", type=int, default=300,
                          help="Fail any test running longer than SECONDS (default 300)")

    def init(self):
        super(TestCommand, self).init()

        self.list_only = self.args.list
        self.include_patterns = self.args.include
        self.exclude_patterns = list()
        self.iterations = self.args.iterations
        self.test_timeout = self.args.timeout

        if self.args.exclude is not None:
            self.exclude_patterns = self.args.exclude

        for module in self.test_modules:
            module.init()

    def run(self):
        if self.list_only:
            for module in self.test_modules:
                module.list_tests()

            return

        sessions = list()

        for i in range(self.iterations):
            for module in self.test_modules:
                session = _TestSession(self)
                sessions.append(session)

                module.run_tests(session)

        total = sum([len(x.tests) for x in sessions])
        skipped = sum([len(x.skipped_tests) for x in sessions])
        failed = sum([len(x.failed_tests) for x in sessions])

        if total == 0:
            self.fail("No tests ran");

        if failed == 0:
            print("RESULT: All tests passed ({} skipped)".format(skipped))
        else:
            print("RESULT: {} {} failed ({} skipped)".format \
                  (failed, _plural("test", failed), skipped))
            _sys.exit(1)

class _TestSession(object):
    def __init__(self, module):
        self.module = module

        self.tests = list()
        self.skipped_tests = list()
        self.passed_tests = list()
        self.failed_tests = list()

class _TestFunction(object):
    def __init__(self, module, function):
        self.module = module
        self.function = function

        self.module.test_functions.append(self)
        self.module.test_functions_by_name[self.name] = self

    def __call__(self, session):
        return self.function(session)

    def __repr__(self):
        return "test '{0}:{1}'".format(self.module.name, self.name)

    @property
    def name(self):
        return self.function.__name__

class _TestModule(object):
    def __init__(self, command, module):
        self.command = command
        self.module = module

        self.open_function = None
        self.close_function = None

        self.test_functions = list()
        self.test_functions_by_name = dict()

        self.command.test_modules.append(self)

    def __repr__(self):
        return "module '{0}'".format(self.name)

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

        functions = dict(_inspect.getmembers(self.module, _inspect.isroutine)).values()

        def line_number(function):
            try:
                return function.__code__.co_firstlineno
            except AttributeError:
                return 0

        def is_test_function(name):
            for prefix in self.command.test_prefixes:
                if name.startswith(prefix):
                    return True

        def included(names):
            if len(self.command.include_patterns) == 0:
                return True

            for pattern in self.command.include_patterns:
                 if _fnmatch.filter(names, pattern):
                     return True

        def excluded(names):
            for pattern in self.command.exclude_patterns:
                if _fnmatch.filter(names, pattern):
                    return True

        for function in sorted(functions, key=lambda x: line_number(x)):
            name = function.__name__
            full_name = "{0}:{1}".format(self.name, name)
            short_name = name[5:]
            names = [name, full_name, short_name]

            if not is_test_function(name):
                continue

            if not included(names):
                self.command.info("Skipping test '{0}' (not included)", full_name)
                continue

            if excluded(names):
                self.command.info("Skipping test '{0}' (excluded)", full_name)
                continue

            _TestFunction(self, function)

    def list_tests(self):
        for function in self.test_functions:
            print("{0}:{1}".format(self.name, function.name))

    def run_tests(self, session):
        if not self.command.verbose:
            self.command.notice("Running tests from {0}", self)

        if self.open_function is not None:
            self.open_function(session)

        try:
            for function in self.test_functions:
                self.run_test(session, function)
        finally:
            if self.close_function is not None:
                self.close_function(session)

    def run_test(self, session, function):
        session.tests.append(function)

        start_time = _time.time()

        if self.command.verbose:
            self.command.notice("Running {0}", function)

            try:
                with _Timer(self.command.test_timeout):
                    function(session)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                if isinstance(e, TestSkipped):
                    session.skipped_tests.append(function)

                    self.command.notice("{0} SKIPPED ({1})", function, _elapsed_time(start_time))
                    _traceback.print_exc()

                    return

                session.failed_tests.append(function)

                if isinstance(e, TestTimedOut):
                    self.command.error("Test timed out")
                else:
                    _traceback.print_exc()

                self.command.error("{0} FAILED ({1})", function, _elapsed_time(start_time))

                return

            session.passed_tests.append(function)

            self.command.notice("{0} PASSED ({1})", function, _elapsed_time(start_time))
        else:
            self._print("{0:.<72} ".format(function.name + " "), end="")

            output_file = _tempfile.mkstemp(prefix="commandant-")[1]

            try:
                with open(output_file, "w") as out:
                    with _OutputRedirected(out, out):
                        with _Timer(self.command.test_timeout):
                            function(session)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                if isinstance(e, TestSkipped):
                    session.skipped_tests.append(function)

                    self._print("SKIPPED {0:>6}".format(_elapsed_time(start_time)))
                    self._print("Reason: {}".format(str(e)))

                    return

                session.failed_tests.append(function)

                self._print("FAILED  {0:>6}".format(_elapsed_time(start_time)))
                self._print("--- Error ---")

                if isinstance(e, TestTimedOut):
                    self._print("> Test timed out")
                elif isinstance(e, _subprocess.CalledProcessError):
                    self._print("> {}".format(str(e)))
                else:
                    lines = _traceback.format_exc().rstrip().split("\n")
                    lines = ["> {}".format(x) for x in lines]

                    self._print("\n".join(lines))

                self._print("--- Output ---")

                if not self.command.quiet:
                    with open(output_file, "r") as out:
                        for line in out:
                            _sys.stdout.write("> ")
                            _sys.stdout.write(line)

                    _sys.stdout.flush()

                return
            finally:
                _os.remove(output_file)

            session.passed_tests.append(function)

            self._print("PASSED  {0:>6}".format(_elapsed_time(start_time)))

    def _print(self, *args, **kwargs):
        if self.command.quiet:
            return

        print(*args, **kwargs)
        _sys.stdout.flush()
        _sys.stderr.flush()

def _elapsed_time(start_time):
    elapsed = _time.time() - start_time

    if elapsed > 240:
        return "{0:.0f}m".format(elapsed / 60)

    if elapsed > 60:
        return "{0:.0f}s".format(elapsed)

    return "{0:.1f}s".format(elapsed)

def _plural(noun, count=0):
    if noun is None:
        return ""

    if count == 1:
        return noun

    if noun.endswith("s"):
        return "{}ses".format(noun)

    return "{}s".format(noun)

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

class _Timer(object):
    def __init__(self, seconds):
        self.seconds = seconds

    def __enter__(self):
        _signal.signal(_signal.SIGALRM, self.raise_timeout)
        _signal.alarm(self.seconds)

    def __exit__(self, exc_type, exc_value, traceback):
        _signal.alarm(0)

    def raise_timeout(self, *args):
        raise TestTimedOut()
