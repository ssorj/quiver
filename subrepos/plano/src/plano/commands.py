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

from .main import *
from .main import _capitalize_help

import argparse as _argparse
import code as _code
import collections as _collections
import importlib as _importlib
import inspect as _inspect
import os as _os
import sys as _sys

class PlanoTestCommand(BaseCommand):
    def __init__(self, test_modules=[]):
        super(PlanoTestCommand, self).__init__()

        self.test_modules = test_modules

        if _inspect.ismodule(self.test_modules):
            self.test_modules = [self.test_modules]

        self.parser = BaseArgumentParser()
        self.parser.add_argument("include", metavar="PATTERN", nargs="*", default=["*"],
                                 help="Run tests with names matching PATTERN (default '*', all tests)")
        self.parser.add_argument("-e", "--exclude", metavar="PATTERN", action="append", default=[],
                                 help="Do not run tests with names matching PATTERN (repeatable)")
        self.parser.add_argument("-m", "--module", action="append", default=[],
                                 help="Collect tests from MODULE.  This option can be repeated.")
        self.parser.add_argument("-l", "--list", action="store_true",
                                 help="Print the test names and exit")
        self.parser.add_argument("--enable", metavar="PATTERN", action="append", default=[],
                                 help=_argparse.SUPPRESS)
        self.parser.add_argument("--unskip", metavar="PATTERN", action="append", default=[],
                                 help="Run skipped tests matching PATTERN (repeatable)")
        self.parser.add_argument("--timeout", metavar="SECONDS", type=int, default=300,
                                 help="Fail any test running longer than SECONDS (default 300)")
        self.parser.add_argument("--fail-fast", action="store_true",
                                 help="Exit on the first failure encountered in a test run")
        self.parser.add_argument("--iterations", metavar="COUNT", type=int, default=1,
                                 help="Run the tests COUNT times (default 1)")

    def parse_args(self, args):
        return self.parser.parse_args(args)

    def init(self, args):
        self.list_only = args.list
        self.include_patterns = args.include
        self.exclude_patterns = args.exclude
        self.enable_patterns = args.enable
        self.unskip_patterns = args.unskip
        self.timeout = args.timeout
        self.fail_fast = args.fail_fast
        self.iterations = args.iterations

        try:
            for name in args.module:
                self.test_modules.append(_importlib.import_module(name))
        except ImportError as e:
            raise PlanoError(e)

    def run(self):
        if self.list_only:
            print_tests(self.test_modules)
            return

        for i in range(self.iterations):
            run_tests(self.test_modules, include=self.include_patterns,
                      exclude=self.exclude_patterns,
                      enable=self.enable_patterns, unskip=self.unskip_patterns,
                      test_timeout=self.timeout, fail_fast=self.fail_fast,
                      verbose=self.verbose, quiet=self.quiet)

class PlanoCommand(BaseCommand):
    def __init__(self, planofile=None):
        self.planofile = planofile

        description = "Run commands defined as Python functions"

        self.pre_parser = BaseArgumentParser(description=description, add_help=False)
        self.pre_parser.add_argument("-h", "--help", action="store_true",
                                     help="Show this help message and exit")

        if self.planofile is None:
            self.pre_parser.add_argument("-f", "--file",
                                         help="Load commands from FILE (default 'Planofile' or '.planofile')")

        self.parser = _argparse.ArgumentParser(parents=(self.pre_parser,),
                                               description=description, add_help=False, allow_abbrev=False)

        self.bound_commands = _collections.OrderedDict()
        self.running_commands = list()

        self.default_command_name = None
        self.default_command_args = None
        self.default_command_kwargs = None

    def set_default_command(self, name, *args, **kwargs):
        self.default_command_name = name
        self.default_command_args = args
        self.default_command_kwargs = kwargs

    def parse_args(self, args):
        pre_args, _ = self.pre_parser.parse_known_args(args)

        self._load_config(getattr(pre_args, "file", None))
        self._process_commands()

        return self.parser.parse_args(args)

    def init(self, args):
        self.help = args.help

        self.selected_command = None
        self.command_args = list()
        self.command_kwargs = dict()

        if args.command is None:
            if self.default_command_name is not None:
                self.selected_command = self.bound_commands[self.default_command_name]
                self.command_args = self.default_command_args
                self.command_kwargs = self.default_command_kwargs
        else:
            self.selected_command = self.bound_commands[args.command]

            for arg in self.selected_command.args.values():
                if arg.positional:
                    if arg.multiple:
                        self.command_args.extend(getattr(args, arg.name))
                    else:
                        self.command_args.append(getattr(args, arg.name))
                else:
                    self.command_kwargs[arg.name] = getattr(args, arg.name)

    def run(self):
        if self.help or self.selected_command is None:
            self.parser.print_help()
            return

        with Timer() as timer:
            self.selected_command(self, *self.command_args, **self.command_kwargs)

        cprint("OK", color="green", file=_sys.stderr, end="")
        cprint(" ({})".format(format_duration(timer.elapsed_time)), color="magenta", file=_sys.stderr)

    def _bind_commands(self, scope):
        for var in scope.values():
            if callable(var) and var.__class__.__name__ == "Command":
                self.bound_commands[var.name] = var

    def _load_config(self, planofile):
        if planofile is None:
            planofile = self.planofile

        if planofile is not None and is_dir(planofile):
            planofile = self._find_planofile(planofile)

        if planofile is not None and not is_file(planofile):
            exit("Planofile '{}' not found", planofile)

        if planofile is None:
            planofile = self._find_planofile(get_current_dir())

        if planofile is None:
            return

        debug("Loading '{}'", planofile)

        _sys.path.insert(0, join(get_parent_dir(planofile), "python"))

        scope = dict(globals())
        scope["app"] = self

        try:
            with open(planofile) as f:
                exec(f.read(), scope)
        except Exception as e:
            error(e)
            exit("Failure loading {}: {}", repr(planofile), str(e))

        self._bind_commands(scope)

    def _find_planofile(self, dir):
        for name in ("Planofile", ".planofile"):
            path = join(dir, name)

            if is_file(path):
                return path

    def _process_commands(self):
        subparsers = self.parser.add_subparsers(title="commands", dest="command")

        for command in self.bound_commands.values():
            subparser = subparsers.add_parser(command.name, help=command.help,
                                              description=nvl(command.description, command.help),
                                              formatter_class=_argparse.RawDescriptionHelpFormatter)

            for arg in command.args.values():
                if arg.positional:
                    if arg.multiple:
                        subparser.add_argument(arg.name, metavar=arg.metavar, type=arg.type, help=arg.help, nargs="*")
                    elif arg.optional:
                        subparser.add_argument(arg.name, metavar=arg.metavar, type=arg.type, help=arg.help, nargs="?", default=arg.default)
                    else:
                        subparser.add_argument(arg.name, metavar=arg.metavar, type=arg.type, help=arg.help)
                else:
                    flag_args = list()

                    if arg.short_option is not None:
                        flag_args.append("-{}".format(arg.short_option))

                    flag_args.append("--{}".format(arg.display_name))

                    help = arg.help

                    if arg.default not in (None, False):
                        if help is None:
                            help = "Default value is {}".format(repr(arg.default))
                        else:
                            help += " (default {})".format(repr(arg.default))

                    if arg.default is False:
                        subparser.add_argument(*flag_args, dest=arg.name, default=arg.default, action="store_true", help=help)
                    else:
                        subparser.add_argument(*flag_args, dest=arg.name, default=arg.default, metavar=arg.metavar, type=arg.type, help=help)

            _capitalize_help(subparser)

class PlanoShellCommand(BaseCommand):
    def __init__(self):
        self.parser = BaseArgumentParser()
        self.parser.add_argument("file", metavar="FILE", nargs="?",
                                 help="Read program from FILE")
        self.parser.add_argument("arg", metavar="ARG", nargs="*",
                                 help="Program arguments")
        self.parser.add_argument("-c", "--command",
                                 help="A program passed in as a string")
        self.parser.add_argument("-i", "--interactive", action="store_true",
                                 help="Operate interactively after running the program (if any)")

    def parse_args(self, args):
        return self.parser.parse_args(args)

    def init(self, args):
        self.file = args.file
        self.interactive = args.interactive
        self.command = args.command

    def run(self):
        stdin_isatty = _os.isatty(_sys.stdin.fileno())
        script = None

        if self.file == "-": # pragma: nocover
            script = _sys.stdin.read()
        elif self.file is not None:
            try:
                with open(self.file) as f:
                    script = f.read()
            except IOError as e:
                raise PlanoError(e)
        elif not stdin_isatty: # pragma: nocover
            # Stdin is a pipe
            script = _sys.stdin.read()

        if self.command is not None:
            exec(self.command, globals())

        if script is not None:
            global ARGS
            ARGS = ARGS[1:]

            exec(script, globals())

        if (self.command is None and self.file is None and stdin_isatty) or self.interactive: # pragma: nocover
            _code.InteractiveConsole(locals=globals()).interact()

def plano(): # pragma: nocover
    PlanoCommand().main()

def planosh(): # pragma: nocover
    PlanoShellCommand().main()

def plano_test(): # pragma: nocover
    PlanoTestCommand().main()
