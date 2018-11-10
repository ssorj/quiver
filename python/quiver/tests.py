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

import sys as _sys

from commandant import *
from plano import *
from quiver.common import *

def open_test_session(session):
    enable_logging("warn")

# Commands

def test_command_quiver(session):
    _test_command("quiver")
    call("quiver --init-only q0")

def test_command_quiver_arrow(session):
    _test_command("quiver-arrow")
    call("quiver-arrow --init-only send q0")

def test_command_quiver_server(session):
    _test_command("quiver-server")
    call("quiver-server --init-only q0")

def test_command_quiver_bench(session):
    _test_command("quiver-bench")
    call("quiver-bench --init-only")

# Arrows

def test_arrow_activemq_artemis_jms(session):
    _test_arrow("activemq-artemis-jms")

def test_arrow_activemq_jms(session):
    _test_arrow("activemq-jms")

def test_arrow_qpid_jms(session):
    _test_arrow("qpid-jms")

def test_arrow_qpid_messaging_cpp(session):
    _test_arrow("qpid-messaging-cpp")

def test_arrow_qpid_messaging_python(session):
    _test_arrow("qpid-messaging-python")

def test_arrow_qpid_proton_c(session):
    raise TestSkipped("Disabled: https://github.com/ssorj/quiver/issues/51")
    _test_arrow("qpid-proton-c")

def test_arrow_qpid_proton_cpp(session):
    raise TestSkipped("Disabled: https://github.com/ssorj/quiver/issues/51")
    _test_arrow("qpid-proton-cpp")

def test_arrow_qpid_proton_python(session):
    _test_arrow("qpid-proton-python")

def test_arrow_rhea(session):
    _test_arrow("rhea")

def test_arrow_vertx_proton(session):
    _test_arrow("vertx-proton")

# Servers

def test_server_activemq(session):
    _test_server("activemq")

def test_server_activemq_artemis(session):
    _test_server("activemq-artemis")

def test_server_builtin(session):
    _test_server("builtin")

def test_server_qpid_cpp(session):
    _test_server("qpid-cpp")

def test_server_qpid_dispatch(session):
    _test_server("qpid-dispatch")

# Pairs

# qpid-jms

def test_pair_qpid_jms_to_qpid_jms(session):
    _test_pair("qpid-jms", "qpid-jms")

def test_pair_qpid_jms_to_qpid_messaging_cpp(session):
    _test_pair("qpid-jms", "qpid-messaging-cpp")

def test_pair_qpid_jms_to_qpid_messaging_python(session):
    _test_pair("qpid-jms", "qpid-messaging-python")

def test_pair_qpid_jms_to_qpid_proton_cpp(session):
    _test_pair("qpid-jms", "qpid-proton-cpp")

def test_pair_qpid_jms_to_qpid_proton_c(session):
    _test_pair("qpid-jms", "qpid-proton-c")

def test_pair_qpid_jms_to_qpid_proton_python(session):
    _test_pair("qpid-jms", "qpid-proton-python")

def test_pair_qpid_jms_to_rhea(session):
    _test_pair("qpid-jms", "rhea")

def test_pair_qpid_jms_to_vertx_proton(session):
    _test_pair("qpid-jms", "vertx-proton")

# qpid-messaging-cpp

def test_pair_qpid_messaging_cpp_to_qpid_jms(session):
    _test_pair("qpid-messaging-cpp", "qpid-jms")

def test_pair_qpid_messaging_cpp_to_qpid_messaging_cpp(session):
    _test_pair("qpid-messaging-cpp", "qpid-messaging-cpp")

def test_pair_qpid_messaging_cpp_to_qpid_messaging_python(session):
    _test_pair("qpid-messaging-cpp", "qpid-messaging-python")

def test_pair_qpid_messaging_cpp_to_qpid_proton_cpp(session):
    _test_pair("qpid-messaging-cpp", "qpid-proton-cpp")

def test_pair_qpid_messaging_cpp_to_qpid_proton_c(session):
    _test_pair("qpid-messaging-cpp", "qpid-proton-c")

def test_pair_qpid_messaging_cpp_to_qpid_proton_python(session):
    _test_pair("qpid-messaging-cpp", "qpid-proton-python")

def test_pair_qpid_messaging_cpp_to_rhea(session):
    _test_pair("qpid-messaging-cpp", "rhea")

def test_pair_qpid_messaging_cpp_to_vertx_proton(session):
    _test_pair("qpid-messaging-cpp", "vertx-proton")

# qpid-messaging-python

def test_pair_qpid_messaging_python_to_qpid_jms(session):
    _test_pair("qpid-messaging-python", "qpid-jms")

def test_pair_qpid_messaging_python_to_qpid_messaging_cpp(session):
    _test_pair("qpid-messaging-python", "qpid-messaging-cpp")

def test_pair_qpid_messaging_python_to_qpid_messaging_python(session):
    _test_pair("qpid-messaging-python", "qpid-messaging-python")

def test_pair_qpid_messaging_python_to_qpid_proton_cpp(session):
    _test_pair("qpid-messaging-python", "qpid-proton-cpp")

def test_pair_qpid_messaging_python_to_qpid_proton_c(session):
    _test_pair("qpid-messaging-python", "qpid-proton-c")

def test_pair_qpid_messaging_python_to_qpid_proton_python(session):
    _test_pair("qpid-messaging-python", "qpid-proton-python")

def test_pair_qpid_messaging_python_to_rhea(session):
    _test_pair("qpid-messaging-python", "rhea")

def test_pair_qpid_messaging_python_to_vertx_proton(session):
    _test_pair("qpid-messaging-python", "vertx-proton")

# qpid-proton-cpp

def test_pair_qpid_proton_cpp_to_qpid_jms(session):
    _test_pair("qpid-proton-cpp", "qpid-jms")

def test_pair_qpid_proton_cpp_to_qpid_messaging_cpp(session):
    _test_pair("qpid-proton-cpp", "qpid-messaging-cpp")

def test_pair_qpid_proton_cpp_to_qpid_messaging_python(session):
    _test_pair("qpid-proton-cpp", "qpid-messaging-python")

def test_pair_qpid_proton_cpp_to_qpid_proton_cpp(session):
    _test_pair("qpid-proton-cpp", "qpid-proton-cpp")

def test_pair_qpid_proton_cpp_to_qpid_proton_c(session):
    _test_pair("qpid-proton-cpp", "qpid-proton-c")

def test_pair_qpid_proton_cpp_to_qpid_proton_python(session):
    _test_pair("qpid-proton-cpp", "qpid-proton-python")

def test_pair_qpid_proton_cpp_to_rhea(session):
    _test_pair("qpid-proton-cpp", "rhea")

def test_pair_qpid_proton_cpp_to_vertx_proton(session):
    _test_pair("qpid-proton-cpp", "vertx-proton")

# qpid-proton-c

def test_pair_qpid_proton_c_to_qpid_jms(session):
    _test_pair("qpid-proton-c", "qpid-jms")

def test_pair_qpid_proton_c_to_qpid_messaging_cpp(session):
    _test_pair("qpid-proton-c", "qpid-messaging-cpp")

def test_pair_qpid_proton_c_to_qpid_messaging_python(session):
    _test_pair("qpid-proton-c", "qpid-messaging-python")

def test_pair_qpid_proton_c_to_qpid_proton_cpp(session):
    _test_pair("qpid-proton-c", "qpid-proton-cpp")

def test_pair_qpid_proton_c_to_qpid_proton_c(session):
    _test_pair("qpid-proton-c", "qpid-proton-c")

def test_pair_qpid_proton_c_to_qpid_proton_python(session):
    _test_pair("qpid-proton-c", "qpid-proton-python")

def test_pair_qpid_proton_c_to_rhea(session):
    _test_pair("qpid-proton-c", "rhea")

def test_pair_qpid_proton_c_to_vertx_proton(session):
    _test_pair("qpid-proton-c", "vertx-proton")

# qpid-proton-python

def test_pair_qpid_proton_python_to_qpid_jms(session):
    _test_pair("qpid-proton-python", "qpid-jms")

def test_pair_qpid_proton_python_to_qpid_messaging_cpp(session):
    _test_pair("qpid-proton-python", "qpid-messaging-cpp")

def test_pair_qpid_proton_python_to_qpid_messaging_python(session):
    _test_pair("qpid-proton-python", "qpid-messaging-python")

def test_pair_qpid_proton_python_to_qpid_proton_cpp(session):
    _test_pair("qpid-proton-python", "qpid-proton-cpp")

def test_pair_qpid_proton_python_to_qpid_proton_c(session):
    _test_pair("qpid-proton-python", "qpid-proton-c")

def test_pair_qpid_proton_python_to_qpid_proton_python(session):
    _test_pair("qpid-proton-python", "qpid-proton-python")

def test_pair_qpid_proton_python_to_rhea(session):
    _test_pair("qpid-proton-python", "rhea")

def test_pair_qpid_proton_python_to_vertx_proton(session):
    _test_pair("qpid-proton-python", "vertx-proton")

# rhea

def test_pair_rhea_to_qpid_jms(session):
    _test_pair("rhea", "qpid-jms")

def test_pair_rhea_to_qpid_messaging_cpp(session):
    _test_pair("rhea", "qpid-messaging-cpp")

def test_pair_rhea_to_qpid_messaging_python(session):
    _test_pair("rhea", "qpid-messaging-python")

def test_pair_rhea_to_qpid_proton_cpp(session):
    _test_pair("rhea", "qpid-proton-cpp")

def test_pair_rhea_to_qpid_proton_c(session):
    _test_pair("rhea", "qpid-proton-c")

def test_pair_rhea_to_qpid_proton_python(session):
    _test_pair("rhea", "qpid-proton-python")

def test_pair_rhea_to_rhea(session):
    _test_pair("rhea", "rhea")

def test_pair_rhea_to_vertx_proton(session):
    _test_pair("rhea", "vertx-proton")

# vertx-proton

def test_pair_vertx_proton_to_qpid_jms(session):
    _test_pair("vertx-proton", "qpid-jms")

def test_pair_vertx_proton_to_qpid_messaging_cpp(session):
    _test_pair("vertx-proton", "qpid-messaging-cpp")

def test_pair_vertx_proton_to_qpid_messaging_python(session):
    _test_pair("vertx-proton", "qpid-messaging-python")

def test_pair_vertx_proton_to_qpid_proton_cpp(session):
    _test_pair("vertx-proton", "qpid-proton-cpp")

def test_pair_vertx_proton_to_qpid_proton_c(session):
    _test_pair("vertx-proton", "qpid-proton-c")

def test_pair_vertx_proton_to_qpid_proton_python(session):
    _test_pair("vertx-proton", "qpid-proton-python")

def test_pair_vertx_proton_to_rhea(session):
    _test_pair("vertx-proton", "rhea")

def test_pair_vertx_proton_to_vertx_proton(session):
    _test_pair("vertx-proton", "vertx-proton")

def test_bench(session):
    with temp_working_dir() as output:
        command = [
            "quiver-bench",
            "--count", "1",
            "--include-servers", "builtin",
            "--verbose",
            "--output", output,
        ]

        call(command)

class _TestServer(object):
    def __init__(self, impl="builtin", **kwargs):
        port = random_port()

        if impl == "activemq":
            port = "5672"

        self.url = "//127.0.0.1:{}/q0".format(port)
        self.ready_file = make_temp_file()

        command = [
            "quiver-server", self.url,
            "--verbose",
            "--ready-file", self.ready_file,
            "--impl", impl,
        ]

        self.proc = start_process(command, **kwargs)
        self.proc.url = self.url

    def __enter__(self):
        for i in range(30):
            if read(self.ready_file) == "ready\n":
                break

            sleep(0.2)

        return self.proc

    def __exit__(self, exc_type, exc_value, traceback):
        stop_process(self.proc)
        remove(self.ready_file)

def _test_url():
    return "//127.0.0.1:{}/q0".format(random_port())

def _test_command(command):
    call("{} --help", command)
    call("{} --version", command)

def _test_arrow(impl):
    if not impl_available(impl):
        raise TestSkipped("Arrow '{}' is unavailable".format(impl))

    call("quiver-arrow --impl {} --info", impl)

    if impl in AMQP_ARROW_IMPLS:
        with _TestServer() as server:
            call("quiver-arrow send {} --impl {} --count 1 --verbose", server.url, impl)
            call("quiver-arrow receive {} --impl {} --count 1 --verbose", server.url, impl)

            call("quiver-arrow send {} --impl {} --duration 1 --verbose", server.url, impl)
            call("quiver-arrow receive {} --impl {} --duration 1 --verbose", server.url, impl)

def _test_server(impl):
    if not impl_available(impl):
        raise TestSkipped("Server '{}' is unavailable".format(impl))

    call("quiver-server --impl {} --info", impl)

    if impl == "activemq-artemis":
        # quiver-server: Calling '/home/jross/code/quiver/build/quiver/impls/quiver-server-activemq-artemis
        #     127.0.0.1 49183 q0 /run/user/1000/plano-inagdcaw'
        # java.lang.reflect.InvocationTargetException
        #       at sun.reflect.NativeMethodAccessorImpl.invoke0(Native Method)
        #       ...
        #       at org.apache.activemq.artemis.boot.Artemis.<clinit>(Artemis.java:40)
        # Caused by: java.io.FileNotFoundException: /var/lib/artemis/log/artemis.log (Permission denied)

        raise TestSkipped("Permissions problem")

    with _TestServer(impl=impl) as server:
        call("quiver {} --count 1", server.url)

def _test_pair(sender_impl, receiver_impl):
    if not impl_available(sender_impl):
        raise TestSkipped("Sender '{}' is unavailable".format(sender_impl))

    if not impl_available(receiver_impl):
        raise TestSkipped("Receiver '{}' is unavailable".format(receiver_impl))

    if receiver_impl in PEER_TO_PEER_ARROW_IMPLS:
        call("quiver {} --sender {} --receiver {} --count 1 --peer-to-peer --verbose",
             _test_url(), sender_impl, receiver_impl)

    with _TestServer() as server:
        call("quiver {} --sender {} --receiver {} --count 1 --verbose",
             server.url, sender_impl, receiver_impl)
