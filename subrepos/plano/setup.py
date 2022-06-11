#!/usr/bin/python3
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

import collections
import os
import tempfile

from distutils.core import setup
from distutils.command.build_scripts import build_scripts
from distutils.file_util import copy_file

class _build_scripts(build_scripts):
    def run(self):
        try:
            prefix = self.distribution.command_options["install"]["prefix"][1]
        except KeyError:
            try:
                self.distribution.command_options["install"]["user"]
            except KeyError:
                prefix = "/usr/local"
            else:
                prefix = os.path.join(os.path.expanduser("~"), ".local")

        temp_dir = tempfile.mkdtemp()
        default_home = os.path.join(prefix, "lib", "plano")

        for name in os.listdir("bin"):
            if name.endswith(".in"):
                in_path = os.path.join("bin", name)
                out_path = os.path.join(temp_dir, name[:-3])

                content = open(in_path).read()
                content = content.replace("@default_home@", default_home)
                open(out_path, "w").write(content)

                self.scripts.remove(in_path)
                self.scripts.append(out_path)

        super(_build_scripts, self).run()

def find_data_files(dir, output_prefix):
    data_files = collections.defaultdict(list)

    for root, dirs, files in os.walk(dir):
        for name in files:
            data_files[os.path.join(output_prefix, root)].append(os.path.join(root, name))

    return [(k, v) for k, v in data_files.items()]

setup(name="plano",
      version="1.0.0-SNAPSHOT",
      url="https://github.com/ssorj/plano",
      author="Justin Ross",
      author_email="justin.ross@gmail.com",
      cmdclass={'build_scripts': _build_scripts},
      py_modules=["plano"],
      package_dir={"": "python"},
      data_files=[("lib/plano/python", ["python/plano_tests.py",
                                        "python/bullseye.py",
                                        "python/bullseye.strings",
                                        "python/bullseye_tests.py"]),
                  *find_data_files("test-project", "lib/plano")],
      scripts=["bin/plano", "bin/planosh", "bin/planotest", "bin/plano-self-test.in"])
