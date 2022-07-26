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

from plano import *

@test
def hello():
    print("Hello")

@test
def goodbye():
    print("Goodbye")

@test(disabled=True)
def badbye():
    print("Badbye")
    assert False

@test(disabled=True)
def skipped():
    skip_test("Skipped")
    assert False

@test(disabled=True)
def keyboard_interrupt():
    raise KeyboardInterrupt()

@test(disabled=True, timeout=0.05)
def timeout():
    sleep(10, quiet=True)
    assert False

@test(disabled=True)
def process_error():
    run("expr 1 / 0")

@test(disabled=True)
def system_exit():
    exit(1)
