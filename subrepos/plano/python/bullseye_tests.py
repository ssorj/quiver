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

from bullseye import *
from plano import *

from bullseye import test as test_command

test_project_dir = join(get_parent_dir(get_parent_dir(__file__)), "test-project")
result_file = "build/result.json"

class test_project(working_dir):
    def __enter__(self):
        dir = super(test_project, self).__enter__()
        copy(test_project_dir, ".", inside=False)
        return dir

def run_plano(*args):
    PlanoCommand().main(["-f", join(test_project_dir, "Planofile")] + list(args))

@test
def project_operations():
    project.name = "alphabet"

    with project_env():
        assert "ALPHABET_HOME" in ENV, ENV

    with working_dir():
        input_file = write("zeta-file", "X@replace-me@X")
        output_file = configure_file(input_file, "zeta-file", {"replace-me": "Y"})
        output = read(output_file)
        assert output == "XYX", output

@test
def build_command():
    with test_project():
        run_plano("build")

        result = read_json(result_file)
        assert result["built"], result

        check_file("build/bin/chucker")
        check_file("build/bin/chucker-test")
        check_file("build/chucker/python/chucker.py")
        check_file("build/chucker/python/chucker_tests.py")

        result = read("build/bin/chucker").strip()
        assert result.endswith(".local/lib/chucker"), result

        result = read_json("build/build.json")
        assert result["prefix"].endswith(".local"), result

        run_plano("build", "--clean", "--prefix", "/usr/local")

        result = read("build/bin/chucker").strip()
        assert result == "/usr/local/lib/chucker", result

        result = read_json("build/build.json")
        assert result["prefix"] == ("/usr/local"), result

@test
def test_command():
    with test_project():
        run_plano("test")

        check_file(result_file)

        result = read_json(result_file)
        assert result["tested"], result

        run_plano("test", "--verbose")
        run_plano("test", "--list")
        run_plano("test", "--include", "test_hello")
        run_plano("test", "--clean")

@test
def install_command():
    with test_project():
        run_plano("install", "--staging-dir", "staging")

        result = read_json(result_file)
        assert result["installed"], result

        check_dir("staging")

    with test_project():
        assert not exists("build"), list_dir()

        run_plano("build", "--prefix", "/opt/local")
        run_plano("install", "--staging-dir", "staging")

        check_dir("staging/opt/local")

@test
def clean_command():
    with test_project():
        run_plano("build")

        check_dir("build")

        run_plano("clean")

        assert not is_dir("build")

@test
def env_command():
    with test_project():
        run_plano("env")
        run_plano("env", "--undo")

@test
def generate_command():
    with test_project():
        run_plano("generate", "README.md")

        assert exists("README.md"), list_dir()

        run_plano("generate", "--stdout", "LICENSE.txt")

        assert not exists("LICENSE.txt"), list_dir()

        run_plano("generate", "all")

        assert exists(".gitignore"), list_dir()
        assert exists("LICENSE.txt"), list_dir()
        assert exists("VERSION.txt"), list_dir()

        with expect_system_exit():
            run_plano("generate", "no-such-file")
