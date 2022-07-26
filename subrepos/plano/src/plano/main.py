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
import base64 as _base64
import binascii as _binascii
import code as _code
import codecs as _codecs
import collections as _collections
import fnmatch as _fnmatch
import getpass as _getpass
import inspect as _inspect
import json as _json
import os as _os
import pprint as _pprint
import pkgutil as _pkgutil
import random as _random
import re as _re
import shlex as _shlex
import shutil as _shutil
import signal as _signal
import socket as _socket
import subprocess as _subprocess
import sys as _sys
import tempfile as _tempfile
import time as _time
import traceback as _traceback
import urllib as _urllib
import uuid as _uuid

_max = max

## Exceptions

class PlanoException(Exception):
    pass

class PlanoError(PlanoException):
    pass

class PlanoTimeout(PlanoException):
    pass

class PlanoTestSkipped(Exception):
    pass

## Global variables

ENV = _os.environ
ARGS = _sys.argv

STDIN = _sys.stdin
STDOUT = _sys.stdout
STDERR = _sys.stderr
DEVNULL = _os.devnull

LINUX = _sys.platform == "linux"
WINDOWS = _sys.platform in ("win32", "cygwin")

PLANO_DEBUG = "PLANO_DEBUG" in ENV

## Archive operations

def make_archive(input_dir, output_file=None, quiet=False):
    """
    group: archive_operations
    """

    check_program("tar")

    archive_stem = get_base_name(input_dir)

    if output_file is None:
        output_file = "{}.tar.gz".format(join(get_current_dir(), archive_stem))

    _info(quiet, "Making archive {} from directory {}", repr(output_file), repr(input_dir))

    with working_dir(get_parent_dir(input_dir)):
        run("tar -czf temp.tar.gz {}".format(archive_stem))
        move("temp.tar.gz", output_file)

    return output_file

def extract_archive(input_file, output_dir=None, quiet=False):
    check_program("tar")

    if output_dir is None:
        output_dir = get_current_dir()

    _info(quiet, "Extracting archive {} to directory {}", repr(input_file), repr(output_dir))

    input_file = get_absolute_path(input_file)

    with working_dir(output_dir):
        copy(input_file, "temp.tar.gz")

        try:
            run("tar -xf temp.tar.gz")
        finally:
            remove("temp.tar.gz")

    return output_dir

def rename_archive(input_file, new_archive_stem, quiet=False):
    _info(quiet, "Renaming archive {} with stem {}", repr(input_file), repr(new_archive_stem))

    output_dir = get_absolute_path(get_parent_dir(input_file))
    output_file = "{}.tar.gz".format(join(output_dir, new_archive_stem))

    input_file = get_absolute_path(input_file)

    with working_dir():
        extract_archive(input_file)

        input_name = list_dir()[0]
        input_dir = move(input_name, new_archive_stem)

        make_archive(input_dir, output_file=output_file)

    remove(input_file)

    return output_file

## Command operations

class BaseCommand(object):
    def main(self, args=None):
        args = self.parse_args(args)

        assert args is None or isinstance(args, _argparse.Namespace), args

        self.verbose = args.verbose or args.debug
        self.quiet = args.quiet
        self.debug_enabled = args.debug
        self.init_only = args.init_only

        level = "notice"

        if self.verbose:
            level = "info"

        if self.quiet:
            level = "error"

        if self.debug_enabled:
            level = "debug"

        with logging_enabled(level=level):
            try:
                self.init(args)

                if self.init_only:
                    return

                self.run()
            except KeyboardInterrupt:
                pass
            except PlanoError as e:
                if self.debug_enabled:
                    _traceback.print_exc()
                    exit(1)
                else:
                    exit(str(e))

    def parse_args(self, args): # pragma: nocover
        raise NotImplementedError()

    def init(self, args): # pragma: nocover
        pass

    def run(self): # pragma: nocover
        raise NotImplementedError()

class BaseArgumentParser(_argparse.ArgumentParser):
    def __init__(self, **kwargs):
        super(BaseArgumentParser, self).__init__(**kwargs)

        self.allow_abbrev = False
        self.formatter_class = _argparse.RawDescriptionHelpFormatter

        self.add_argument("--verbose", action="store_true",
                          help="Print detailed logging to the console")
        self.add_argument("--quiet", action="store_true",
                          help="Print no logging to the console")
        self.add_argument("--debug", action="store_true",
                          help="Print debugging output to the console")
        self.add_argument("--init-only", action="store_true",
                          help=_argparse.SUPPRESS)

        _capitalize_help(self)

# Patch the default help text
def _capitalize_help(parser):
    try:
        for action in parser._actions:
            if action.help and action.help is not _argparse.SUPPRESS:
                action.help = capitalize(action.help)
    except: # pragma: nocover
        pass

## Console operations

def flush():
    _sys.stdout.flush()
    _sys.stderr.flush()

def eprint(*args, **kwargs):
    print(*args, file=_sys.stderr, **kwargs)

def pprint(*args, **kwargs):
    args = [pformat(x) for x in args]
    print(*args, **kwargs)

_color_codes = {
    "black": "\u001b[30",
    "red": "\u001b[31",
    "green": "\u001b[32",
    "yellow": "\u001b[33",
    "blue": "\u001b[34",
    "magenta": "\u001b[35",
    "cyan": "\u001b[36",
    "white": "\u001b[37",
}

_color_reset = "\u001b[0m"

def _get_color_code(color, bright):
    elems = [_color_codes[color]]

    if bright:
        elems.append(";1")

    elems.append("m")

    return "".join(elems)

def _is_color_enabled(file):
    return hasattr(file, "isatty") and file.isatty()

class console_color(object):
    def __init__(self, color=None, bright=False, file=_sys.stdout):
        self.file = file
        self.color_code = None

        if (color, bright) != (None, False):
            self.color_code = _get_color_code(color, bright)

        self.enabled = self.color_code is not None and _is_color_enabled(self.file)

    def __enter__(self):
        if self.enabled:
            print(self.color_code, file=self.file, end="", flush=True)

    def __exit__(self, exc_type, exc_value, traceback):
        if self.enabled:
            print(_color_reset, file=self.file, end="", flush=True)

def cformat(value, color=None, bright=False, file=_sys.stdout):
    if (color, bright) != (None, False) and _is_color_enabled(file):
        return "".join((_get_color_code(color, bright), value, _color_reset))
    else:
        return value

def cprint(*args, **kwargs):
    color = kwargs.pop("color", "white")
    bright = kwargs.pop("bright", False)
    file = kwargs.get("file", _sys.stdout)

    with console_color(color, bright=bright, file=file):
        print(*args, **kwargs)

class output_redirected(object):
    def __init__(self, output, quiet=False):
        self.output = output
        self.quiet = quiet

    def __enter__(self):
        flush()

        _info(self.quiet, "Redirecting output to file {}", repr(self.output))

        if is_string(self.output):
            output = open(self.output, "w")

        self.prev_stdout, self.prev_stderr = _sys.stdout, _sys.stderr
        _sys.stdout, _sys.stderr = output, output

    def __exit__(self, exc_type, exc_value, traceback):
        flush()

        _sys.stdout, _sys.stderr = self.prev_stdout, self.prev_stderr

try:
    breakpoint
except NameError: # pragma: nocover
    def breakpoint():
        import pdb
        pdb.set_trace()

def repl(vars): # pragma: nocover
    _code.InteractiveConsole(locals=vars).interact()

def print_properties(props, file=None):
    size = max([len(x[0]) for x in props])

    for prop in props:
        name = "{}:".format(prop[0])
        template = "{{:<{}}}  ".format(size + 1)

        print(template.format(name), prop[1], end="", file=file)

        for value in prop[2:]:
            print(" {}".format(value), end="", file=file)

        print(file=file)

## Directory operations

def find(dirs=None, include="*", exclude=()):
    if dirs is None:
        dirs = "."

    if is_string(dirs):
        dirs = (dirs,)

    if is_string(include):
        include = (include,)

    if is_string(exclude):
        exclude = (exclude,)

    found = set()

    for dir in dirs:
        for root, dir_names, file_names in _os.walk(dir):
            names = dir_names + file_names

            for include_pattern in include:
                names = _fnmatch.filter(names, include_pattern)

                for exclude_pattern in exclude:
                    for name in _fnmatch.filter(names, exclude_pattern):
                        names.remove(name)

                if root.startswith("./"):
                    root = remove_prefix(root, "./")
                elif root == ".":
                    root = ""

                found.update([join(root, x) for x in names])

    return sorted(found)

def make_dir(dir, quiet=False):
    if dir == "":
        return dir

    if not exists(dir):
        _info(quiet, "Making directory '{}'", dir)
        _os.makedirs(dir)

    return dir

def make_parent_dir(path, quiet=False):
    return make_dir(get_parent_dir(path), quiet=quiet)

# Returns the current working directory so you can change it back
def change_dir(dir, quiet=False):
    _debug(quiet, "Changing directory to {}", repr(dir))

    prev_dir = get_current_dir()

    if not dir:
        return prev_dir

    _os.chdir(dir)

    return prev_dir

def list_dir(dir=None, include="*", exclude=()):
    if dir in (None, ""):
        dir = get_current_dir()

    assert is_dir(dir), dir

    if is_string(include):
        include = (include,)

    if is_string(exclude):
        exclude = (exclude,)

    names = _os.listdir(dir)

    for include_pattern in include:
        names = _fnmatch.filter(names, include_pattern)

        for exclude_pattern in exclude:
            for name in _fnmatch.filter(names, exclude_pattern):
                names.remove(name)

    return sorted(names)

# No args constructor gets a temp dir
class working_dir(object):
    def __init__(self, dir=None, quiet=False):
        self.dir = dir
        self.prev_dir = None
        self.remove = False
        self.quiet = quiet

        if self.dir is None:
            self.dir = make_temp_dir()
            self.remove = True

    def __enter__(self):
        if self.dir == ".":
            return

        _info(self.quiet, "Entering directory {}", repr(get_absolute_path(self.dir)))

        make_dir(self.dir, quiet=True)

        self.prev_dir = change_dir(self.dir, quiet=True)

        return self.dir

    def __exit__(self, exc_type, exc_value, traceback):
        if self.dir == ".":
            return

        _debug(self.quiet, "Returning to directory {}", repr(get_absolute_path(self.prev_dir)))

        change_dir(self.prev_dir, quiet=True)

        if self.remove:
            remove(self.dir, quiet=True)

## Environment operations

def join_path_var(*paths):
    return _os.pathsep.join(unique(skip(paths)))

def get_current_dir():
    return _os.getcwd()

def get_home_dir(user=None):
    return _os.path.expanduser("~{}".format(user or ""))

def get_user():
    return _getpass.getuser()

def get_hostname():
    return _socket.gethostname()

def get_program_name(command=None):
    if command is None:
        args = ARGS
    else:
        args = command.split()

    for arg in args:
        if "=" not in arg:
            return get_base_name(arg)

def which(program_name):
    return _shutil.which(program_name)

def check_env(var, message=None):
    if var not in _os.environ:
        if message is None:
            message = "Environment variable {} is not set".format(repr(var))

        raise PlanoError(message)

def check_module(module, message=None):
    if _pkgutil.find_loader(module) is None:
        if message is None:
            message = "Module {} is not found".format(repr(module))

        raise PlanoError(message)

def check_program(program, message=None):
    if which(program) is None:
        if message is None:
            message = "Program {} is not found".format(repr(program))

        raise PlanoError(message)

class working_env(object):
    def __init__(self, **vars):
        self.amend = vars.pop("amend", True)
        self.vars = vars

    def __enter__(self):
        self.prev_vars = dict(_os.environ)

        if not self.amend:
            for name, value in list(_os.environ.items()):
                if name not in self.vars:
                    del _os.environ[name]

        for name, value in self.vars.items():
            _os.environ[name] = str(value)

    def __exit__(self, exc_type, exc_value, traceback):
        for name, value in self.prev_vars.items():
            _os.environ[name] = value

        for name, value in self.vars.items():
            if name not in self.prev_vars:
                del _os.environ[name]

class working_module_path(object):
    def __init__(self, path, amend=True):
        if is_string(path):
            if not is_absolute(path):
                path = get_absolute_path(path)

            path = [path]

        if amend:
            path = path + _sys.path

        self.path = path

    def __enter__(self):
        self.prev_path = _sys.path
        _sys.path = self.path

    def __exit__(self, exc_type, exc_value, traceback):
        _sys.path = self.prev_path

def print_env(file=None):
    props = (
        ("ARGS", ARGS),
        ("ENV['PATH']", ENV.get("PATH")),
        ("ENV['PYTHONPATH']", ENV.get("PYTHONPATH")),
        ("sys.executable", _sys.executable),
        ("sys.path", _sys.path),
        ("sys.version", _sys.version.replace("\n", "")),
        ("get_current_dir()", get_current_dir()),
        ("get_home_dir()", get_home_dir()),
        ("get_hostname()", get_hostname()),
        ("get_program_name()", get_program_name()),
        ("get_user()", get_user()),
        ("plano.__file__", __file__),
        ("which('plano')", which("plano")),
    )

    print_properties(props, file=file)

## File operations

def touch(file, quiet=False):
    _info(quiet, "Touching {}", repr(file))

    try:
        _os.utime(file, None)
    except OSError:
        append(file, "")

    return file

# symlinks=True - Preserve symlinks
# inside=True - Place from_path inside to_path if to_path is a directory
def copy(from_path, to_path, symlinks=True, inside=True, quiet=False):
    _info(quiet, "Copying {} to {}", repr(from_path), repr(to_path))

    if is_dir(to_path) and inside:
        to_path = join(to_path, get_base_name(from_path))
    else:
        make_parent_dir(to_path, quiet=True)

    if is_dir(from_path):
        for name in list_dir(from_path):
            copy(join(from_path, name), join(to_path, name), symlinks=symlinks, inside=False, quiet=True)

        _shutil.copystat(from_path, to_path)
    elif is_link(from_path) and symlinks:
        make_link(to_path, read_link(from_path), quiet=True)
    else:
        _shutil.copy2(from_path, to_path)

    return to_path

# inside=True - Place from_path inside to_path if to_path is a directory
def move(from_path, to_path, inside=True, quiet=False):
    _info(quiet, "Moving {} to {}", repr(from_path), repr(to_path))

    to_path = copy(from_path, to_path, inside=inside, quiet=True)
    remove(from_path, quiet=True)

    return to_path

def remove(paths, quiet=False):
    if is_string(paths):
        paths = (paths,)

    for path in paths:
        if not exists(path):
            continue

        _debug(quiet, "Removing {}", repr(path))

        if is_dir(path):
            _shutil.rmtree(path, ignore_errors=True)
        else:
            _os.remove(path)

def get_file_size(file):
    return _os.path.getsize(file)

## IO operations

def read(file):
    with _codecs.open(file, encoding="utf-8", mode="r") as f:
        return f.read()

def write(file, string):
    make_parent_dir(file, quiet=True)

    with _codecs.open(file, encoding="utf-8", mode="w") as f:
        f.write(string)

    return file

def append(file, string):
    make_parent_dir(file, quiet=True)

    with _codecs.open(file, encoding="utf-8", mode="a") as f:
        f.write(string)

    return file

def prepend(file, string):
    orig = read(file)
    return write(file, string + orig)

def tail(file, count):
    return "".join(tail_lines(file, count))

def read_lines(file):
    with _codecs.open(file, encoding="utf-8", mode="r") as f:
        return f.readlines()

def write_lines(file, lines):
    make_parent_dir(file, quiet=True)

    with _codecs.open(file, encoding="utf-8", mode="w") as f:
        f.writelines(lines)

    return file

def append_lines(file, lines):
    make_parent_dir(file, quiet=True)

    with _codecs.open(file, encoding="utf-8", mode="a") as f:
        f.writelines(lines)

    return file

def prepend_lines(file, lines):
    orig_lines = read_lines(file)

    make_parent_dir(file, quiet=True)

    with _codecs.open(file, encoding="utf-8", mode="w") as f:
        f.writelines(lines)
        f.writelines(orig_lines)

    return file

def tail_lines(file, count):
    assert count >= 0

    with _codecs.open(file, encoding="utf-8", mode="r") as f:
        pos = count + 1
        lines = list()

        while len(lines) <= count:
            try:
                f.seek(-pos, 2)
            except IOError:
                f.seek(0)
                break
            finally:
                lines = f.readlines()

            pos *= 2

        return lines[-count:]

def replace_in_file(file, expr, replacement, count=0):
    write(file, replace(read(file), expr, replacement, count=count))

def concatenate(file, input_files):
    assert file not in input_files

    make_parent_dir(file, quiet=True)

    with open(file, "wb") as f:
        for input_file in input_files:
            if not exists(input_file):
                continue

            with open(input_file, "rb") as inf:
                _shutil.copyfileobj(inf, f)

## Iterable operations

def unique(iterable):
    return list(_collections.OrderedDict.fromkeys(iterable).keys())

def skip(iterable, values=(None, "", (), [], {})):
    if is_scalar(values):
        values = (values,)

    items = list()

    for item in iterable:
        if item not in values:
            items.append(item)

    return items

## JSON operations

def read_json(file):
    with _codecs.open(file, encoding="utf-8", mode="r") as f:
        return _json.load(f)

def write_json(file, data):
    make_parent_dir(file, quiet=True)

    with _codecs.open(file, encoding="utf-8", mode="w") as f:
        _json.dump(data, f, indent=4, separators=(",", ": "), sort_keys=True)

    return file

def parse_json(json):
    return _json.loads(json)

def emit_json(data):
    return _json.dumps(data, indent=4, separators=(",", ": "), sort_keys=True)

## HTTP operations

def _run_curl(method, url, content=None, content_file=None, content_type=None, output_file=None, insecure=False):
    check_program("curl")

    options = [
        "-sf",
        "-X", method,
        "-H", "'Expect:'",
    ]

    if content is not None:
        assert content_file is None
        options.extend(("-d", "@-"))

    if content_file is not None:
        assert content is None, content
        options.extend(("-d", "@{}".format(content_file)))

    if content_type is not None:
        options.extend(("-H", "'Content-Type: {}'".format(content_type)))

    if output_file is not None:
        options.extend(("-o", output_file))

    if insecure:
        options.append("--insecure")

    options = " ".join(options)
    command = "curl {} {}".format(options, url)

    if output_file is None:
        return call(command, input=content)
    else:
        make_parent_dir(output_file, quiet=True)
        run(command, input=content)

def http_get(url, output_file=None, insecure=False):
    return _run_curl("GET", url, output_file=output_file, insecure=insecure)

def http_get_json(url, insecure=False):
    return parse_json(http_get(url, insecure=insecure))

def http_put(url, content, content_type=None, insecure=False):
    _run_curl("PUT", url, content=content, content_type=content_type, insecure=insecure)

def http_put_file(url, content_file, content_type=None, insecure=False):
    _run_curl("PUT", url, content_file=content_file, content_type=content_type, insecure=insecure)

def http_put_json(url, data, insecure=False):
    http_put(url, emit_json(data), content_type="application/json", insecure=insecure)

def http_post(url, content, content_type=None, output_file=None, insecure=False):
    return _run_curl("POST", url, content=content, content_type=content_type, output_file=output_file, insecure=insecure)

def http_post_file(url, content_file, content_type=None, output_file=None, insecure=False):
    return _run_curl("POST", url, content_file=content_file, content_type=content_type, output_file=output_file, insecure=insecure)

def http_post_json(url, data, insecure=False):
    return parse_json(http_post(url, emit_json(data), content_type="application/json", insecure=insecure))

## Link operations

def make_link(path, linked_path, quiet=False):
    _info(quiet, "Making link {} to {}", repr(path), repr(linked_path))

    make_parent_dir(path, quiet=True)
    remove(path, quiet=True)

    _os.symlink(linked_path, path)

    return path

def read_link(path):
    return _os.readlink(path)

## Logging operations

_logging_levels = (
    "debug",
    "info",
    "notice",
    "warn",
    "error",
    "disabled",
)

_DEBUG = _logging_levels.index("debug")
_INFO = _logging_levels.index("info")
_NOTICE = _logging_levels.index("notice")
_WARN = _logging_levels.index("warn")
_ERROR = _logging_levels.index("error")
_DISABLED = _logging_levels.index("disabled")

_logging_output = None
_logging_threshold = _NOTICE

def enable_logging(level="notice", output=None):
    assert level in _logging_levels

    info("Enabling logging (level={}, output={})", repr(level), repr(nvl(output, "stderr")))

    global _logging_threshold
    _logging_threshold = _logging_levels.index(level)

    if is_string(output):
        output = open(output, "w")

    global _logging_output
    _logging_output = output

def disable_logging():
    info("Disabling logging")

    global _logging_threshold
    _logging_threshold = _DISABLED

class logging_enabled(object):
    def __init__(self, level="notice", output=None):
        self.level = level
        self.output = output

    def __enter__(self):
        self.prev_level = _logging_levels[_logging_threshold]
        self.prev_output = _logging_output

        if self.level == "disabled":
            disable_logging()
        else:
            enable_logging(level=self.level, output=self.output)

    def __exit__(self, exc_type, exc_value, traceback):
        if self.prev_level == "disabled":
            disable_logging()
        else:
            enable_logging(level=self.prev_level, output=self.prev_output)

class logging_disabled(logging_enabled):
    def __init__(self):
        super(logging_disabled, self).__init__(level="disabled")

def fail(message, *args):
    error(message, *args)

    if isinstance(message, BaseException):
        raise message

    raise PlanoError(message.format(*args))

def error(message, *args):
    log(_ERROR, message, *args)

def warn(message, *args):
    log(_WARN, message, *args)

def notice(message, *args):
    log(_NOTICE, message, *args)

def info(message, *args):
    log(_INFO, message, *args)

def debug(message, *args):
    log(_DEBUG, message, *args)

def log(level, message, *args):
    if is_string(level):
        level = _logging_levels.index(level)

    if _logging_threshold <= level:
        _print_message(level, message, args)

def _print_message(level, message, args):
    out = nvl(_logging_output, _sys.stderr)
    exception = None

    if isinstance(message, BaseException):
        exception = message
        message = "{}: {}".format(type(message).__name__, str(message))
    else:
        message = str(message)

    if args:
        message = message.format(*args)

    program = "{}:".format(get_program_name())

    level_color = ("cyan", "cyan", "blue", "yellow", "red", None)[level]
    level_bright = (False, False, False, False, True, False)[level]
    level = cformat("{:>6}:".format(_logging_levels[level]), color=level_color, bright=level_bright, file=out)

    print(program, level, capitalize(message), file=out)

    if exception is not None and hasattr(exception, "__traceback__"):
        _traceback.print_exception(type(exception), exception, exception.__traceback__, file=out)

    out.flush()

def _debug(quiet, message, *args):
    if quiet:
        debug(message, *args)
    else:
        notice(message, *args)

def _info(quiet, message, *args):
    if quiet:
        info(message, *args)
    else:
        notice(message, *args)

## Path operations

def get_absolute_path(path):
    return _os.path.abspath(path)

def normalize_path(path):
    return _os.path.normpath(path)

def get_real_path(path):
    return _os.path.realpath(path)

def get_relative_path(path, start=None):
    return _os.path.relpath(path, start=start)

def get_file_url(path):
    return "file:{}".format(get_absolute_path(path))

def exists(path):
    return _os.path.lexists(path)

def is_absolute(path):
    return _os.path.isabs(path)

def is_dir(path):
    return _os.path.isdir(path)

def is_file(path):
    return _os.path.isfile(path)

def is_link(path):
    return _os.path.islink(path)

def join(*paths):
    path = _os.path.join(*paths)
    path = normalize_path(path)

    return path

def split(path):
    path = normalize_path(path)
    parent, child = _os.path.split(path)

    return parent, child

def split_extension(path):
    path = normalize_path(path)
    root, ext = _os.path.splitext(path)

    return root, ext

def get_parent_dir(path):
    path = normalize_path(path)
    parent, child = split(path)

    return parent

def get_base_name(path):
    path = normalize_path(path)
    parent, name = split(path)

    return name

def get_name_stem(file):
    name = get_base_name(file)

    if name.endswith(".tar.gz"):
        name = name[:-3]

    stem, ext = split_extension(name)

    return stem

def get_name_extension(file):
    name = get_base_name(file)
    stem, ext = split_extension(name)

    return ext

def _check_path(path, test_func, message):
    if not test_func(path):
        parent_dir = get_parent_dir(path)

        if is_dir(parent_dir):
            found_paths = ", ".join([repr(x) for x in list_dir(parent_dir)])
            message = "{}. The parent directory contains: {}".format(message.format(repr(path)), found_paths)
        else:
            message = "{}".format(message.format(repr(path)))

        raise PlanoError(message)

def check_exists(path):
    _check_path(path, exists, "File or directory {} not found")

def check_file(path):
    _check_path(path, is_file, "File {} not found")

def check_dir(path):
    _check_path(path, is_dir, "Directory {} not found")

def await_exists(path, timeout=30, quiet=False):
    _info(quiet, "Waiting for path {} to exist", repr(path))

    timeout_message = "Timed out waiting for path {} to exist".format(path)
    period = 0.03125

    with Timer(timeout=timeout, timeout_message=timeout_message) as timer:
        while True:
            try:
                check_exists(path)
            except PlanoError:
                sleep(period, quiet=True)
                period = min(1, period * 2)
            else:
                return

## Port operations

def get_random_port(min=49152, max=65535):
    ports = [_random.randint(min, max) for _ in range(3)]

    for port in ports:
        try:
            check_port(port)
        except PlanoError:
            return port

    raise PlanoError("Random ports unavailable")

def check_port(port, host="localhost"):
    sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
    sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)

    if sock.connect_ex((host, port)) != 0:
        raise PlanoError("Port {} (host {}) is not reachable".format(repr(port), repr(host)))

def await_port(port, host="localhost", timeout=30, quiet=False):
    _info(quiet, "Waiting for port {}", port)

    if is_string(port):
        port = int(port)

    timeout_message = "Timed out waiting for port {} to open".format(port)
    period = 0.03125

    with Timer(timeout=timeout, timeout_message=timeout_message) as timer:
        while True:
            try:
                check_port(port, host=host)
            except PlanoError:
                sleep(period, quiet=True)
                period = min(1, period * 2)
            else:
                return

## Process operations

def get_process_id():
    return _os.getpid()

def _format_command(command, represent=True):
    if not is_string(command):
        command = " ".join(command)

    if represent:
        return repr(command)
    else:
        return command

# quiet=False - Don't log at notice level
# stash=False - No output unless there is an error
# output=<file> - Send stdout and stderr to a file
# stdin=<file> - XXX
# stdout=<file> - Send stdout to a file
# stderr=<file> - Send stderr to a file
# shell=False - XXX
def start(command, stdin=None, stdout=None, stderr=None, output=None, shell=False, stash=False, quiet=False):
    _info(quiet, "Starting command {}", _format_command(command))

    if output is not None:
        stdout, stderr = output, output

    if is_string(stdin):
        stdin = open(stdin, "r")

    if is_string(stdout):
        stdout = open(stdout, "w")

    if is_string(stderr):
        stderr = open(stderr, "w")

    if stdin is None:
        stdin = _sys.stdin

    if stdout is None:
        stdout = _sys.stdout

    if stderr is None:
        stderr = _sys.stderr

    stash_file = None

    if stash:
        stash_file = make_temp_file()
        out = open(stash_file, "w")
        stdout = out
        stderr = out

    if shell:
        if is_string(command):
            args = command
        else:
            args = " ".join(command)
    else:
        if is_string(command):
            args = _shlex.split(command)
        else:
            args = command

    try:
        proc = PlanoProcess(args, stdin=stdin, stdout=stdout, stderr=stderr, shell=shell, close_fds=True, stash_file=stash_file)
    except OSError as e:
        raise PlanoError("Command {}: {}".format(_format_command(command), str(e)))

    debug("{} started", proc)

    return proc

def stop(proc, timeout=None, quiet=False):
    _info(quiet, "Stopping {}", proc)

    if proc.poll() is not None:
        if proc.exit_code == 0:
            debug("{} already exited normally", proc)
        elif proc.exit_code == -(_signal.SIGTERM):
            debug("{} was already terminated", proc)
        else:
            debug("{} already exited with code {}", proc, proc.exit_code)

        return proc

    kill(proc, quiet=True)

    return wait(proc, timeout=timeout, quiet=True)

def kill(proc, quiet=False):
    _info(quiet, "Killing {}", proc)

    proc.terminate()

def wait(proc, timeout=None, check=False, quiet=False):
    _info(quiet, "Waiting for {} to exit", proc)

    try:
        proc.wait(timeout=timeout)
    except _subprocess.TimeoutExpired:
        raise PlanoTimeout()

    if proc.exit_code == 0:
        debug("{} exited normally", proc)
    elif proc.exit_code < 0:
        debug("{} was terminated by signal {}", proc, abs(proc.exit_code))
    else:
        debug("{} exited with code {}", proc, proc.exit_code)

    if proc.stash_file is not None:
        if proc.exit_code > 0:
            eprint(read(proc.stash_file), end="")

        if not WINDOWS:
            remove(proc.stash_file, quiet=True)

    if check and proc.exit_code > 0:
        raise PlanoProcessError(proc)

    return proc

# input=<string> - Pipe <string> to the process
def run(command, stdin=None, stdout=None, stderr=None, input=None, output=None,
        stash=False, shell=False, check=True, quiet=False):
    _info(quiet, "Running command {}", _format_command(command))

    if input is not None:
        assert stdin in (None, _subprocess.PIPE), stdin

        input = input.encode("utf-8")
        stdin = _subprocess.PIPE

    proc = start(command, stdin=stdin, stdout=stdout, stderr=stderr, output=output,
                 stash=stash, shell=shell, quiet=True)

    proc.stdout_result, proc.stderr_result = proc.communicate(input=input)

    if proc.stdout_result is not None:
        proc.stdout_result = proc.stdout_result.decode("utf-8")

    if proc.stderr_result is not None:
        proc.stderr_result = proc.stderr_result.decode("utf-8")

    return wait(proc, check=check, quiet=True)

# input=<string> - Pipe the given input into the process
def call(command, input=None, shell=False, quiet=False):
    _info(quiet, "Calling {}", _format_command(command))

    proc = run(command, stdin=_subprocess.PIPE, stdout=_subprocess.PIPE, stderr=_subprocess.PIPE,
               input=input, shell=shell, check=True, quiet=True)

    return proc.stdout_result

def exit(arg=None, *args, **kwargs):
    verbose = kwargs.get("verbose", False)

    if arg in (0, None):
        if verbose:
            notice("Exiting normally")

        _sys.exit()

    if is_string(arg):
        if args:
            arg = arg.format(*args)

        if verbose:
            error(arg)

        _sys.exit(arg)

    if isinstance(arg, BaseException):
        if verbose:
            error(arg)

        _sys.exit(str(arg))

    if isinstance(arg, int):
        _sys.exit(arg)

    raise PlanoException("Illegal argument")

_child_processes = list()

class PlanoProcess(_subprocess.Popen):
    def __init__(self, args, **options):
        self.stash_file = options.pop("stash_file", None)

        super(PlanoProcess, self).__init__(args, **options)

        self.args = args
        self.stdout_result = None
        self.stderr_result = None

        _child_processes.append(self)

    @property
    def exit_code(self):
        return self.returncode

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        kill(self)

    def __repr__(self):
        return "process {} (command {})".format(self.pid, _format_command(self.args))

class PlanoProcessError(_subprocess.CalledProcessError, PlanoError):
    def __init__(self, proc):
        super(PlanoProcessError, self).__init__(proc.exit_code, _format_command(proc.args, represent=False))

def _default_sigterm_handler(signum, frame):
    for proc in _child_processes:
        if proc.poll() is None:
            proc.terminate()

    exit(-(_signal.SIGTERM))

_signal.signal(_signal.SIGTERM, _default_sigterm_handler)

## String operations

def replace(string, expr, replacement, count=0):
    return _re.sub(expr, replacement, string, count)

def remove_prefix(string, prefix):
    if string is None:
        return ""

    if prefix and string.startswith(prefix):
        string = string[len(prefix):]

    return string

def remove_suffix(string, suffix):
    if string is None:
        return ""

    if suffix and string.endswith(suffix):
        string = string[:-len(suffix)]

    return string

def shorten(string, max, ellipsis=None):
    assert max is None or isinstance(max, int)

    if string is None:
        return ""

    if max is None or len(string) < max:
        return string
    else:
        if ellipsis is not None:
            string = string + ellipsis
            end = _max(0, max - len(ellipsis))
            return string[0:end] + ellipsis
        else:
            return string[0:max]

def plural(noun, count=0, plural=None):
    if noun in (None, ""):
        return ""

    if count == 1:
        return noun

    if plural is None:
        if noun.endswith("s"):
            plural = "{}ses".format(noun)
        else:
            plural = "{}s".format(noun)

    return plural

def capitalize(string):
    if not string:
        return ""

    return string[0].upper() + string[1:]

def base64_encode(string):
    return _base64.b64encode(string)

def base64_decode(string):
    return _base64.b64decode(string)

def url_encode(string):
    return _urllib.parse.quote_plus(string)

def url_decode(string):
    return _urllib.parse.unquote_plus(string)

## Temp operations

def get_system_temp_dir():
    return _tempfile.gettempdir()

def get_user_temp_dir():
    try:
        return _os.environ["XDG_RUNTIME_DIR"]
    except KeyError:
        return join(get_system_temp_dir(), get_user())

def make_temp_file(suffix="", dir=None):
    if dir is None:
        dir = get_system_temp_dir()

    return _tempfile.mkstemp(prefix="plano-", suffix=suffix, dir=dir)[1]

def make_temp_dir(suffix="", dir=None):
    if dir is None:
        dir = get_system_temp_dir()

    return _tempfile.mkdtemp(prefix="plano-", suffix=suffix, dir=dir)

class temp_file(object):
    def __init__(self, suffix="", dir=None):
        if dir is None:
            dir = get_system_temp_dir()

        self.fd, self.file = _tempfile.mkstemp(prefix="plano-", suffix=suffix, dir=dir)

    def __enter__(self):
        return self.file

    def __exit__(self, exc_type, exc_value, traceback):
        _os.close(self.fd)

        if not WINDOWS: # XXX
            remove(self.file, quiet=True)

class temp_dir(object):
    def __init__(self, suffix="", dir=None):
        self.dir = make_temp_dir(suffix=suffix, dir=dir)

    def __enter__(self):
        return self.dir

    def __exit__(self, exc_type, exc_value, traceback):
        remove(self.dir, quiet=True)

## Time operations

def sleep(seconds, quiet=False):
    _info(quiet, "Sleeping for {} {}", seconds, plural("second", seconds))

    _time.sleep(seconds)

def get_time():
    return _time.time()

def format_duration(duration, align=False):
    assert duration >= 0

    if duration >= 3600:
        value = duration / 3600
        unit = "h"
    elif duration >= 5 * 60:
        value = duration / 60
        unit = "m"
    else:
        value = duration
        unit = "s"

    if align:
        return "{:.1f}{}".format(value, unit)
    elif value > 10:
        return "{:.0f}{}".format(value, unit)
    else:
        return remove_suffix("{:.1f}".format(value), ".0") + unit

class Timer(object):
    def __init__(self, timeout=None, timeout_message=None):
        self.timeout = timeout
        self.timeout_message = timeout_message

        if self.timeout is not None and not hasattr(_signal, "SIGALRM"): # pragma: nocover
            self.timeout = None

        self.start_time = None
        self.stop_time = None

    def start(self):
        self.start_time = get_time()

        if self.timeout is not None:
            self.prev_handler = _signal.signal(_signal.SIGALRM, self.raise_timeout)
            self.prev_timeout, prev_interval = _signal.setitimer(_signal.ITIMER_REAL, self.timeout)
            self.prev_timer_suspend_time = get_time()

            assert prev_interval == 0.0, "This case is not yet handled"

    def stop(self):
        self.stop_time = get_time()

        if self.timeout is not None:
            assert get_time() - self.prev_timer_suspend_time > 0, "This case is not yet handled"

            _signal.signal(_signal.SIGALRM, self.prev_handler)
            _signal.setitimer(_signal.ITIMER_REAL, self.prev_timeout)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()

    @property
    def elapsed_time(self):
        assert self.start_time is not None

        if self.stop_time is None:
            return get_time() - self.start_time
        else:
            return self.stop_time - self.start_time

    def raise_timeout(self, *args):
        raise PlanoTimeout(self.timeout_message)

## Unique ID operations

# Length in bytes, renders twice as long in hex
def get_unique_id(bytes=16):
    assert bytes >= 1
    assert bytes <= 16

    uuid_bytes = _uuid.uuid4().bytes
    uuid_bytes = uuid_bytes[:bytes]

    return _binascii.hexlify(uuid_bytes).decode("utf-8")

## Value operations

def nvl(value, replacement):
    if value is None:
        return replacement

    return value

def is_string(value):
    return isinstance(value, str)

def is_scalar(value):
    return value is None or isinstance(value, (str, int, float, complex, bool))

def is_empty(value):
    return value in (None, "", (), [], {})

def pformat(value):
    return _pprint.pformat(value, width=120)

def format_empty(value, replacement):
    if is_empty(value):
        value = replacement

    return value

def format_not_empty(value, template=None):
    if not is_empty(value) and template is not None:
        value = template.format(value)

    return value

def format_repr(obj, limit=None):
    attrs = ["{}={}".format(k, repr(v)) for k, v in obj.__dict__.items()]
    return "{}({})".format(obj.__class__.__name__, ", ".join(attrs[:limit]))

class Namespace(object):
    def __init__(self, **kwargs):
        for name in kwargs:
            setattr(self, name, kwargs[name])

    def __eq__(self, other):
        return vars(self) == vars(other)

    def __contains__(self, key):
        return key in self.__dict__

    def __repr__(self):
        return format_repr(self)

## YAML operations

def read_yaml(file):
    import yaml as _yaml

    with _codecs.open(file, encoding="utf-8", mode="r") as f:
        return _yaml.safe_load(f)

def write_yaml(file, data):
    import yaml as _yaml

    make_parent_dir(file, quiet=True)

    with _codecs.open(file, encoding="utf-8", mode="w") as f:
        _yaml.safe_dump(data, f)

    return file

def parse_yaml(yaml):
    import yaml as _yaml
    return _yaml.safe_load(yaml)

def emit_yaml(data):
    import yaml as _yaml
    return _yaml.safe_dump(data)

## Test operations

def test(_function=None, name=None, timeout=None, disabled=False):
    class Test(object):
        def __init__(self, function):
            self.function = function
            self.name = nvl(name, self.function.__name__)
            self.timeout = timeout
            self.disabled = disabled

            self.module = _inspect.getmodule(self.function)

            if not hasattr(self.module, "_plano_tests"):
                self.module._plano_tests = list()

            self.module._plano_tests.append(self)

        def __call__(self, test_run, unskipped):
            try:
                self.function()
            except SystemExit as e:
                error(e)
                raise PlanoError("System exit with code {}".format(e))

        def __repr__(self):
            return "test '{}:{}'".format(self.module.__name__, self.name)

    if _function is None:
        return Test
    else:
        return Test(_function)

def skip_test(reason=None):
    if _inspect.stack()[2].frame.f_locals["unskipped"]:
        return

    raise PlanoTestSkipped(reason)

class expect_exception(object):
    def __init__(self, exception_type=Exception, contains=None):
        self.exception_type = exception_type
        self.contains = contains

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_value is None:
            assert False, "Never encountered expected exception {}".format(self.exception_type.__name__)

        if self.contains is None:
            return isinstance(exc_value, self.exception_type)
        else:
            return isinstance(exc_value, self.exception_type) and self.contains in str(exc_value)

class expect_error(expect_exception):
    def __init__(self, contains=None):
        super(expect_error, self).__init__(PlanoError, contains=contains)

class expect_timeout(expect_exception):
    def __init__(self, contains=None):
        super(expect_timeout, self).__init__(PlanoTimeout, contains=contains)

class expect_system_exit(expect_exception):
    def __init__(self, contains=None):
        super(expect_system_exit, self).__init__(SystemExit, contains=contains)

class expect_output(temp_file):
    def __init__(self, equals=None, contains=None, startswith=None, endswith=None):
        super(expect_output, self).__init__()
        self.equals = equals
        self.contains = contains
        self.startswith = startswith
        self.endswith = endswith

    def __exit__(self, exc_type, exc_value, traceback):
        result = read(self.file)

        if self.equals is None:
            assert len(result) > 0, result
        else:
            assert result == self.equals, result

        if self.contains is not None:
            assert self.contains in result, result

        if self.startswith is not None:
            assert result.startswith(self.startswith), result

        if self.endswith is not None:
            assert result.endswith(self.endswith), result

        super(expect_output, self).__exit__(exc_type, exc_value, traceback)

def print_tests(modules):
    if _inspect.ismodule(modules):
        modules = (modules,)

    for module in modules:
        for test in module._plano_tests:
            flags = "(disabled)" if test.disabled else ""
            print(" ".join((str(test), flags)).strip())

def run_tests(modules, include="*", exclude=(), enable=(), unskip=(), test_timeout=300, fail_fast=False, verbose=False, quiet=False):
    if _inspect.ismodule(modules):
        modules = (modules,)

    if is_string(include):
        include = (include,)

    if is_string(exclude):
        exclude = (exclude,)

    if is_string(enable):
        enable = (enable,)

    if is_string(unskip):
        enable = (unskip,)

    test_run = TestRun(test_timeout=test_timeout, fail_fast=fail_fast, verbose=verbose, quiet=quiet)

    if verbose:
        notice("Starting {}", test_run)
    elif not quiet:
        cprint("=== Configuration ===", color="cyan")

        props = (
            ("Modules", format_empty(", ".join([x.__name__ for x in modules]), "[none]")),
            ("Test timeout", format_duration(test_timeout)),
            ("Fail fast", fail_fast),
        )

        print_properties(props)
        print()

    for module in modules:
        if verbose:
            notice("Running tests from module {} (file {})", repr(module.__name__), repr(module.__file__))
        elif not quiet:
            cprint("=== Module {} ===".format(repr(module.__name__)), color="cyan")

        if not hasattr(module, "_plano_tests"):
            warn("Module {} has no tests", repr(module.__name__))
            continue

        for test in module._plano_tests:
            if test.disabled and not any([_fnmatch.fnmatchcase(test.name, x) for x in enable]):
                continue

            included = any([_fnmatch.fnmatchcase(test.name, x) for x in include])
            excluded = any([_fnmatch.fnmatchcase(test.name, x) for x in exclude])
            unskipped = any([_fnmatch.fnmatchcase(test.name, x) for x in unskip])

            if included and not excluded:
                test_run.tests.append(test)
                _run_test(test_run, test, unskipped)

        if not verbose and not quiet:
            print()

    total = len(test_run.tests)
    skipped = len(test_run.skipped_tests)
    failed = len(test_run.failed_tests)

    if total == 0:
        raise PlanoError("No tests ran")

    notes = ""

    if skipped != 0:
        notes = "({} skipped)".format(skipped)

    if failed == 0:
        result_message = "All tests passed {}".format(notes).strip()
    else:
        result_message = "{} {} failed {}".format(failed, plural("test", failed), notes).strip()

    if verbose:
        if failed == 0:
            notice(result_message)
        else:
            error(result_message)
    elif not quiet:
        cprint("=== Summary ===", color="cyan")

        props = (
            ("Total", total),
            ("Skipped", skipped, format_not_empty(", ".join([x.name for x in test_run.skipped_tests]), "({})")),
            ("Failed", failed, format_not_empty(", ".join([x.name for x in test_run.failed_tests]), "({})")),
        )

        print_properties(props)
        print()

        cprint("=== RESULT ===", color="cyan")

        if failed == 0:
            cprint(result_message, color="green")
        else:
            cprint(result_message, color="red", bright="True")

        print()

    if failed != 0:
        raise PlanoError(result_message)

def _run_test(test_run, test, unskipped):
    if test_run.verbose:
        notice("Running {}", test)
    elif not test_run.quiet:
        print("{:.<72} ".format(test.name + " "), end="")

    timeout = nvl(test.timeout, test_run.test_timeout)

    with temp_file() as output_file:
        try:
            with Timer(timeout=timeout) as timer:
                if test_run.verbose:
                    test(test_run, unskipped)
                else:
                    with output_redirected(output_file, quiet=True):
                        test(test_run, unskipped)
        except KeyboardInterrupt:
            raise
        except PlanoTestSkipped as e:
            test_run.skipped_tests.append(test)

            if test_run.verbose:
                notice("{} SKIPPED ({})", test, format_duration(timer.elapsed_time))
            elif not test_run.quiet:
                _print_test_result("SKIPPED", timer, "yellow")
                print("Reason: {}".format(str(e)))
        except Exception as e:
            test_run.failed_tests.append(test)

            if test_run.verbose:
                _traceback.print_exc()

                if isinstance(e, PlanoTimeout):
                    error("{} **FAILED** (TIMEOUT) ({})", test, format_duration(timer.elapsed_time))
                else:
                    error("{} **FAILED** ({})", test, format_duration(timer.elapsed_time))
            elif not test_run.quiet:
                if isinstance(e, PlanoTimeout):
                    _print_test_result("**FAILED** (TIMEOUT)", timer, color="red", bright=True)
                else:
                    _print_test_result("**FAILED**", timer, color="red", bright=True)

                _print_test_error(e)
                _print_test_output(output_file)

            if test_run.fail_fast:
                return True
        else:
            test_run.passed_tests.append(test)

            if test_run.verbose:
                notice("{} PASSED ({})", test, format_duration(timer.elapsed_time))
            elif not test_run.quiet:
                _print_test_result("PASSED", timer)

def _print_test_result(status, timer, color="white", bright=False):
    cprint("{:<7}".format(status), color=color, bright=bright, end="")
    print("{:>6}".format(format_duration(timer.elapsed_time, align=True)))

def _print_test_error(e):
    cprint("--- Error ---", color="yellow")

    if isinstance(e, PlanoProcessError):
        print("> {}".format(str(e)))
    else:
        lines = _traceback.format_exc().rstrip().split("\n")
        lines = ["> {}".format(x) for x in lines]

        print("\n".join(lines))

def _print_test_output(output_file):
    if get_file_size(output_file) == 0:
        return

    cprint("--- Output ---", color="yellow")

    with open(output_file, "r") as out:
        for line in out:
            print("> {}".format(line), end="")

class TestRun(object):
    def __init__(self, test_timeout=None, fail_fast=False, verbose=False, quiet=False):
        self.test_timeout = test_timeout
        self.fail_fast = fail_fast
        self.verbose = verbose
        self.quiet = quiet

        self.tests = list()
        self.skipped_tests = list()
        self.failed_tests = list()
        self.passed_tests = list()

    def __repr__(self):
        return format_repr(self)

## Plano command operations

_command_help = {
    "build":    "Build artifacts from source",
    "clean":    "Clean up the source tree",
    "dist":     "Generate distribution artifacts",
    "install":  "Install the built artifacts on your system",
    "test":     "Run the tests",
}

def command(_function=None, name=None, args=None, parent=None):
    class Command(object):
        def __init__(self, function):
            self.function = function
            self.module = _inspect.getmodule(self.function)

            self.name = name
            self.args = args
            self.parent = parent

            if self.parent is None:
                self.name = nvl(self.name, function.__name__.rstrip("_").replace("_", "-"))
                self.args = self.process_args(self.args)
            else:
                self.name = nvl(self.name, self.parent.name)
                self.args = nvl(self.args, self.parent.args)

            doc = _inspect.getdoc(self.function)

            if doc is None:
                self.help = _command_help.get(self.name)
                self.description = self.help
            else:
                self.help = doc.split("\n")[0]
                self.description = doc

            if self.parent is not None:
                self.help = nvl(self.help, self.parent.help)
                self.description = nvl(self.description, self.parent.description)

            debug("Defining {}", self)

            for arg in self.args.values():
                debug("  {}", str(arg).capitalize())

        def __repr__(self):
            return "command '{}:{}'".format(self.module.__name__, self.name)

        def process_args(self, input_args):
            sig = _inspect.signature(self.function)
            params = list(sig.parameters.values())
            input_args = {x.name: x for x in nvl(input_args, ())}
            output_args = _collections.OrderedDict()

            try:
                app_param = params.pop(0)
            except IndexError:
                raise PlanoError("The function for {} is missing the required 'app' parameter".format(self))
            else:
                if app_param.name != "app":
                    raise PlanoError("The function for {} is missing the required 'app' parameter".format(self))

            for param in params:
                try:
                    arg = input_args[param.name]
                except KeyError:
                    arg = CommandArgument(param.name)

                if param.kind is param.POSITIONAL_ONLY: # pragma: nocover
                    if arg.positional is None:
                        arg.positional = True
                elif param.kind is param.POSITIONAL_OR_KEYWORD and param.default is param.empty:
                    if arg.positional is None:
                        arg.positional = True
                elif param.kind is param.POSITIONAL_OR_KEYWORD and param.default is not param.empty:
                    arg.optional = True
                    arg.default = param.default
                elif param.kind is param.VAR_POSITIONAL:
                    if arg.positional is None:
                        arg.positional = True
                    arg.multiple = True
                elif param.kind is param.VAR_KEYWORD:
                    continue
                elif param.kind is param.KEYWORD_ONLY:
                    arg.optional = True
                    arg.default = param.default
                else: # pragma: nocover
                    raise NotImplementedError(param.kind)

                if arg.type is None and arg.default not in (None, False): # XXX why false?
                    arg.type = type(arg.default)

                output_args[arg.name] = arg

            return output_args

        def __call__(self, app, *args, **kwargs):
            from .commands import PlanoCommand
            assert isinstance(app, PlanoCommand), app

            command = app.bound_commands[self.name]

            if command is not self:
                command(app, *args, **kwargs)
                return

            debug("Running {} {} {}".format(self, args, kwargs))

            app.running_commands.append(self)

            dashes = "--" * len(app.running_commands)
            display_args = list(self.get_display_args(args, kwargs))

            with console_color("magenta", file=_sys.stderr):
                eprint("{}> {}".format(dashes, self.name), end="")

                if display_args:
                    eprint(" ({})".format(", ".join(display_args)), end="")

                eprint()

            self.function(app, *args, **kwargs)

            cprint("<{} {}".format(dashes, self.name), color="magenta", file=_sys.stderr)

            app.running_commands.pop()

            if app.running_commands:
                name = app.running_commands[-1].name

                cprint("{}| {}".format(dashes[:-2], name), color="magenta", file=_sys.stderr)

        def get_display_args(self, args, kwargs):
            for i, arg in enumerate(self.args.values()):
                if arg.positional:
                    if arg.multiple:
                        for va in args[i:]:
                            yield repr(va)
                    elif arg.optional:
                        value = args[i]

                        if value == arg.default:
                            continue

                        yield repr(value)
                    else:
                        yield repr(args[i])
                else:
                    value = kwargs.get(arg.name, arg.default)

                    if value == arg.default:
                        continue

                    if value in (True, False):
                        value = str(value).lower()
                    else:
                        value = repr(value)

                    yield "{}={}".format(arg.display_name, value)

    if _function is None:
        return Command
    else:
        return Command(_function)

class CommandArgument(object):
    def __init__(self, name, display_name=None, type=None, metavar=None, help=None, short_option=None, default=None, positional=None):
        self.name = name
        self.display_name = nvl(display_name, self.name.replace("_", "-"))
        self.type = type
        self.metavar = nvl(metavar, self.display_name.upper())
        self.help = help
        self.short_option = short_option
        self.default = default
        self.positional = positional

        self.optional = False
        self.multiple = False

    def __repr__(self):
        return "argument '{}' (default {})".format(self.name, repr(self.default))

if PLANO_DEBUG: # pragma: nocover
    enable_logging(level="debug")
