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

from __future__ import print_function

import collections as _collections
import fnmatch as _fnmatch
import os as _os
import shutil as _shutil
import sys as _sys

from plano import *

class _Project:
    def __init__(self):
        self.name = None
        self.source_dir = "python"
        self.included_modules = ["*"]
        self.excluded_modules = ["plano", "bullseye"]
        self.data_dirs = []
        self.build_dir = "build"
        self.test_modules = []

project = _Project()

_default_prefix = join(get_home_dir(), ".local")

def check_project():
    assert project.name
    assert project.source_dir
    assert project.build_dir

class project_env(working_env):
    def __init__(self):
        check_project()

        home_var = "{0}_HOME".format(project.name.upper().replace("-", "_"))

        env = {
            home_var: get_absolute_path(join(project.build_dir, project.name)),
            "PATH": get_absolute_path(join(project.build_dir, "bin")) + ":" + ENV["PATH"],
            "PYTHONPATH": get_absolute_path(join(project.build_dir, project.name, project.source_dir)),
        }

        super(project_env, self).__init__(**env)

def configure_file(input_file, output_file, substitutions, quiet=False):
    notice("Configuring '{0}' for output '{1}'", input_file, output_file)

    content = read(input_file)

    for name, value in substitutions.items():
        content = content.replace("@{0}@".format(name), value)

    write(output_file, content)

    _shutil.copymode(input_file, output_file)

    return output_file

_prefix_arg = CommandArgument("prefix", help="The base path for installed files", default=_default_prefix)
_clean_arg = CommandArgument("clean_", help="Clean before starting", display_name="clean")
_verbose_arg = CommandArgument("verbose", help="Print detailed logging to the console")

@command(args=(_prefix_arg, _clean_arg))
def build(app, prefix=None, clean_=False):
    check_project()

    if clean_:
        clean(app)

    build_file = join(project.build_dir, "build.json")
    build_data = {}

    if exists(build_file):
        build_data = read_json(build_file)

    mtime = _os.stat(project.source_dir).st_mtime

    for path in find(project.source_dir):
        mtime = max(mtime, _os.stat(path).st_mtime)

    if prefix is None:
        prefix = build_data.get("prefix", _default_prefix)

    new_build_data = {"prefix": prefix, "mtime": mtime}

    debug("Existing build data: {0}", pformat(build_data))
    debug("New build data:      {0}", pformat(new_build_data))

    if build_data == new_build_data:
        debug("Already built")
        return

    write_json(build_file, new_build_data)

    default_home = join(prefix, "lib", project.name)

    for path in find("bin", "*.in"):
        configure_file(path, join(project.build_dir, path[:-3]), {"default_home": default_home})

    for path in find("bin", exclude="*.in"):
        copy(path, join(project.build_dir, path), inside=False, symlinks=False)

    for path in find(project.source_dir, "*.py"):
        module_name = get_name_stem(path)
        included = any([_fnmatch.fnmatchcase(module_name, x) for x in project.included_modules])
        excluded = any([_fnmatch.fnmatchcase(module_name, x) for x in project.excluded_modules])

        if included and not excluded:
            copy(path, join(project.build_dir, project.name, path), inside=False, symlinks=False)

    for dir_name in project.data_dirs:
        for path in find(dir_name):
            copy(path, join(project.build_dir, project.name, path), inside=False, symlinks=False)

@command(args=(CommandArgument("include", help="Run only tests with names matching PATTERN", metavar="PATTERN"),
               CommandArgument("exclude", help="Do not run tests with names matching PATTERN", metavar="PATTERN"),
               CommandArgument("enable", help="Enable disabled tests matching PATTERN", metavar="PATTERN"),
               CommandArgument("list_", help="Print the test names and exit", display_name="list"),
               _verbose_arg, _clean_arg))
def test(app, include="*", exclude=None, enable=None, list_=False, verbose=False, clean_=False):
    check_project()

    if clean_:
        clean(app)

    if not list_:
        build(app)

    with project_env():
        from plano import _import_module
        modules = [_import_module(x) for x in project.test_modules]

        if not modules: # pragma: nocover
            notice("No tests found")
            return

        args = list()

        if list_:
            print_tests(modules)
            return

        exclude = nvl(exclude, ())
        enable = nvl(enable, ())

        run_tests(modules, include=include, exclude=exclude, enable=enable, verbose=verbose)

@command(args=(CommandArgument("staging_dir", help="A path prepended to installed files"),
               _prefix_arg, _clean_arg))
def install(app, staging_dir="", prefix=None, clean_=False):
    check_project()

    build(app, prefix=prefix, clean_=clean_)

    assert is_dir(project.build_dir), list_dir()

    build_file = join(project.build_dir, "build.json")
    build_data = read_json(build_file)
    build_prefix = project.build_dir + "/"
    install_prefix = staging_dir + build_data["prefix"]

    for path in find(join(project.build_dir, "bin")):
        copy(path, join(install_prefix, remove_prefix(path, build_prefix)), inside=False, symlinks=False)

    for path in find(join(project.build_dir, project.name)):
        copy(path, join(install_prefix, "lib", remove_prefix(path, build_prefix)), inside=False, symlinks=False)

@command
def clean(app):
    check_project()

    remove(project.build_dir)
    remove(find(".", "__pycache__"))
    remove(find(".", "*.pyc"))

@command(args=(CommandArgument("undo", help="Generate settings that restore the previous environment"),))
def env(app, undo=False):
    """
    Generate shell settings for the project environment

    To apply the settings, source the output from your shell:

        $ source <(plano env)
    """

    check_project()

    project_dir = get_current_dir() # XXX Needs some checking
    home_var = "{0}_HOME".format(project.name.upper().replace("-", "_"))
    old_home_var = "OLD_{0}".format(home_var)
    home_dir = join(project_dir, project.build_dir, project.name)

    if undo:
        print("[[ ${0} ]] && export {1}=${2} && unset {3}".format(old_home_var, home_var, old_home_var, old_home_var))
        print("[[ $OLD_PATH ]] && export PATH=$OLD_PATH && unset OLD_PATH")
        print("[[ $OLD_PYTHONPATH ]] && export PYTHONPATH=$OLD_PYTHONPATH && unset OLD_PYTHONPATH")

        return

    print("[[ ${0} ]] && export {1}=${2}".format(home_var, old_home_var, home_var))
    print("[[ $PATH ]] && export OLD_PATH=$PATH")
    print("[[ $PYTHONPATH ]] && export OLD_PYTHONPATH=$PYTHONPATH")

    print("export {0}={1}".format(home_var, home_dir))

    path = [
        join(project_dir, project.build_dir, "bin"),
        ENV.get("PATH", ""),
    ]

    print("export PATH={0}".format(join_path_var(*path)))

    python_path = [
        join(home_dir, project.source_dir),
        join(project_dir, project.source_dir),
        ENV.get("PYTHONPATH", ""),
    ]

    print("export PYTHONPATH={0}".format(join_path_var(*python_path)))

@command(args=(CommandArgument("filename", help="Which file to generate"),
               CommandArgument("stdout", help="Print to stdout instead of writing the file directly")))
def generate(app, filename, stdout=False):
    """
    Generate standard project files

    Use one of the following filenames:

        .gitignore
        LICENSE.txt
        README.md
        VERSION.txt

    Use the special filename "all" to generate all of them.
    """

    assert project.name

    project_files = _StringCatalog(__file__)

    if filename == "all":
        for name in project_files:
            _generate_file(project_files, name, stdout)
    else:
        _generate_file(project_files, filename, stdout)

def _generate_file(project_files, filename, stdout):
    try:
        content = project_files[filename]
    except KeyError:
        exit("File {0} is not one of the options".format(repr(filename)))

    content = content.lstrip()
    content = content.format(project_title=project.name.capitalize(), project_name=project.name)

    if stdout:
        print(content, end="")
    else:
        write(filename, content)

# @command
# def coverage(app):
#     check_program("coverage3")

#     with project_env():
#         run("coverage3 run --include python/qtools/\* build/scripts-3.9/qtools-self-test")
#         run("coverage3 report")
#         run("coverage3 html")

#         print(f"file:{get_current_dir()}/htmlcov/index.html")

class _StringCatalog(dict):
    def __init__(self, path):
        super(_StringCatalog, self).__init__()

        self.path = "{0}.strings".format(split_extension(path)[0])

        check_file(self.path)

        key = None
        out = list()

        for line in read_lines(self.path):
            line = line.rstrip()

            if line.startswith("[") and line.endswith("]"):
                if key:
                    self[key] = "".join(out).strip() + "\n"

                out = list()
                key = line[1:-1]

                continue

            out.append(line)
            out.append("\r\n")

        self[key] = "".join(out).strip() + "\n"

    def __repr__(self):
        return format_repr(self)
