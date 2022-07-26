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
import os as _os

from plano import *
from quiver.common import *
from urllib.parse import urlparse as _urlparse

SCRIPT_DIR = _os.path.dirname(_os.path.realpath(__file__))
TCLIENT_CERTIFICATE_PEM = SCRIPT_DIR + "/test_tls_certs/tclient-certificate.pem"
TCLIENT_PRIVATE_KEY_PEM = SCRIPT_DIR + "/test_tls_certs/tclient-private-key-nopwd.pem"
TSERVER_CERTIFICATE_PEM = SCRIPT_DIR + "/test_tls_certs/tserver-certificate.pem"
TSERVER_PRIVATE_KEY_PEM = SCRIPT_DIR + "/test_tls_certs/tserver-private-key.pem"

# Commands

@test
def command_quiver():
    _test_command("quiver")
    run("quiver --init-only q0")

@test
def command_quiver_arrow():
    _test_command("quiver-arrow")
    run("quiver-arrow --init-only send q0")

@test
def command_quiver_server():
    _test_command("quiver-server")
    run("quiver-server --init-only q0")

@test
def command_quiver_bench():
    with working_dir() as output:
        _test_command("quiver-bench")
        run(f"quiver-bench --init-only --output {output}")

# Arrows

@test
def arrow_activemq_artemis_jms():
    _test_arrow("activemq-artemis-jms")

@test
def arrow_activemq_jms():
    _test_arrow("activemq-jms")

@test
def arrow_qpid_jms():
    _test_arrow("qpid-jms")

@test
def arrow_qpid_proton_c():
    _test_arrow("qpid-proton-c")

@test
def arrow_qpid_proton_cpp():
    _test_arrow("qpid-proton-cpp")

@test
def arrow_qpid_proton_dotnet():
    _test_arrow("qpid-proton-dotnet")

@test
def arrow_qpid_proton_python():
    _test_arrow("qpid-proton-python")

@test
def arrow_qpid_protonj2():
    _test_arrow("qpid-protonj2")

@test
def arrow_rhea():
    _test_arrow("rhea")

@test
def arrow_vertx_proton():
    _test_arrow("vertx-proton")

# Servers

@test
def server_activemq_artemis():
    _test_server("activemq-artemis")

@test
def server_builtin():
    _test_server("builtin")

@test
def server_qpid_dispatch():
    _test_server("qpid-dispatch")

# Pairs

# qpid-jms

@test
def pair_qpid_jms_to_qpid_jms():
    _test_pair("qpid-jms", "qpid-jms")

@test
def pair_qpid_jms_to_qpid_proton_c():
    _test_pair("qpid-jms", "qpid-proton-c")

@test
def pair_qpid_jms_to_qpid_proton_cpp():
    _test_pair("qpid-jms", "qpid-proton-cpp")

@test
def pair_qpid_jms_to_qpid_proton_python():
    _test_pair("qpid-jms", "qpid-proton-python")

@test
def pair_qpid_jms_to_qpid_protonj2():
    _test_pair("qpid-jms", "qpid-protonj2")

@test
def pair_qpid_jms_to_qpid_proton_dotnet():
    _test_pair("qpid-jms", "qpid-proton-dotnet")

@test
def pair_qpid_jms_to_rhea():
    _test_pair("qpid-jms", "rhea")

@test
def pair_qpid_jms_to_vertx_proton():
    _test_pair("qpid-jms", "vertx-proton")

# qpid-proton-c

@test
def pair_qpid_proton_c_to_qpid_jms():
    _test_pair("qpid-proton-c", "qpid-jms")

@test
def pair_qpid_proton_c_to_qpid_proton_c():
    _test_pair("qpid-proton-c", "qpid-proton-c")

@test
def pair_qpid_proton_c_to_qpid_proton_cpp():
    _test_pair("qpid-proton-c", "qpid-proton-cpp")

@test
def pair_qpid_proton_c_to_qpid_proton_python():
    _test_pair("qpid-proton-c", "qpid-proton-python")

@test
def pair_qpid_proton_c_to_qpid_protonj2():
    _test_pair("qpid-proton-c", "qpid-protonj2")

@test
def pair_qpid_proton_c_to_qpid_proton_dotnet():
    _test_pair("qpid-proton-c", "qpid-proton-dotnet")

@test
def pair_qpid_proton_c_to_rhea():
    _test_pair("qpid-proton-c", "rhea")

@test
def pair_qpid_proton_c_to_vertx_proton():
    _test_pair("qpid-proton-c", "vertx-proton")

# qpid-proton-cpp

@test
def pair_qpid_proton_cpp_to_qpid_jms():
    _test_pair("qpid-proton-cpp", "qpid-jms")

@test
def pair_qpid_proton_cpp_to_qpid_proton_c():
    _test_pair("qpid-proton-cpp", "qpid-proton-c")

@test
def pair_qpid_proton_cpp_to_qpid_proton_cpp():
    _test_pair("qpid-proton-cpp", "qpid-proton-cpp")

@test
def pair_qpid_proton_cpp_to_qpid_proton_python():
    _test_pair("qpid-proton-cpp", "qpid-proton-python")

@test
def pair_qpid_proton_cpp_to_qpid_protonj2():
    _test_pair("qpid-proton-cpp", "qpid-protonj2")

@test
def pair_qpid_proton_cpp_to_qpid_proton_dotnet():
    _test_pair("qpid-proton-cpp", "qpid-proton-dotnet")

@test
def pair_qpid_proton_cpp_to_rhea():
    _test_pair("qpid-proton-cpp", "rhea")

@test
def pair_qpid_proton_cpp_to_vertx_proton():
    _test_pair("qpid-proton-cpp", "vertx-proton")

# qpid-proton-python

@test
def pair_qpid_proton_python_to_qpid_jms():
    _test_pair("qpid-proton-python", "qpid-jms")

@test
def pair_qpid_proton_python_to_qpid_proton_c():
    _test_pair("qpid-proton-python", "qpid-proton-c")

@test
def pair_qpid_proton_python_to_qpid_proton_cpp():
    _test_pair("qpid-proton-python", "qpid-proton-cpp")

@test
def pair_qpid_proton_python_to_qpid_proton_python():
    _test_pair("qpid-proton-python", "qpid-proton-python")

@test
def pair_qpid_proton_python_to_qpid_protonj2():
    _test_pair("qpid-proton-python", "qpid-protonj2")

@test
def pair_qpid_proton_python_to_qpid_proton_dotnet():
    _test_pair("qpid-proton-python", "qpid-proton-dotnet")

@test
def pair_qpid_proton_python_to_rhea():
    _test_pair("qpid-proton-python", "rhea")

@test
def pair_qpid_proton_python_to_vertx_proton():
    _test_pair("qpid-proton-python", "vertx-proton")

# qpid-protonj2

@test
def pair_qpid_protonj2_to_qpid_jms():
    _test_pair("qpid-protonj2", "qpid-jms")

@test
def pair_qpid_protonj2_to_qpid_proton_c():
    _test_pair("qpid-protonj2", "qpid-proton-c")

@test
def pair_qpid_protonj2_to_qpid_proton_cpp():
    _test_pair("qpid-protonj2", "qpid-proton-cpp")

@test
def pair_qpid_protonj2_to_qpid_proton_python():
    _test_pair("qpid-protonj2", "qpid-proton-python")

@test
def pair_qpid_protonj2_to_qpid_protonj2():
    _test_pair("qpid-protonj2", "qpid-protonj2")

@test
def pair_qpid_protonj2_to_qpid_proton_dotnet():
    _test_pair("qpid-protonj2", "qpid-proton-dotnet")

@test
def pair_qpid_protonj2_to_rhea():
    skip_test("Some kind of message encoding interop problem")
    _test_pair("qpid-protonj2", "rhea")

@test
def pair_qpid_protonj2_to_vertx_proton():
    _test_pair("qpid-protonj2", "vertx-proton")

# qpid-proton-dotnet

@test
def pair_qpid_proton_dotnet_to_qpid_jms():
    _test_pair("qpid-proton-dotnet", "qpid-jms")

@test
def pair_qpid_proton_dotnet_to_qpid_proton_c():
    _test_pair("qpid-proton-dotnet", "qpid-proton-c")

@test
def pair_qpid_proton_dotnet_to_qpid_proton_cpp():
    _test_pair("qpid-proton-dotnet", "qpid-proton-cpp")

@test
def pair_qpid_proton_dotnet_to_qpid_proton_python():
    _test_pair("qpid-proton-dotnet", "qpid-proton-python")

@test
def pair_qpid_proton_dotnet_to_qpid_protonj2():
    _test_pair("qpid-proton-dotnet", "qpid-protonj2")

@test
def pair_qpid_proton_dotnet_to_qpid_proton_dotnet():
    _test_pair("qpid-proton-dotnet", "qpid-proton-dotnet")

@test
def pair_qpid_proton_dotnet_to_rhea():
    skip_test("Some kind of message encoding interop problem")
    _test_pair("qpid-proton-dotnet", "rhea")

@test
def pair_qpid_proton_dotnet_to_vertx_proton():
    _test_pair("qpid-proton-dotnet", "vertx-proton")

# rhea

@test
def pair_rhea_to_qpid_jms():
    _test_pair("rhea", "qpid-jms")

@test
def pair_rhea_to_qpid_proton_c():
    _test_pair("rhea", "qpid-proton-c")

@test
def pair_rhea_to_qpid_proton_cpp():
    _test_pair("rhea", "qpid-proton-cpp")

@test
def pair_rhea_to_qpid_proton_python():
    _test_pair("rhea", "qpid-proton-python")

@test
def pair_rhea_to_qpid_protonj2():
    _test_pair("rhea", "qpid-protonj2")

@test
def pair_rhea_to_qpid_proton_dotnet():
    _test_pair("rhea", "qpid-proton-dotnet")

@test
def pair_rhea_to_rhea():
    _test_pair("rhea", "rhea")

@test
def pair_rhea_to_vertx_proton():
    _test_pair("rhea", "vertx-proton")

# vertx-proton

@test
def pair_vertx_proton_to_qpid_jms():
    _test_pair("vertx-proton", "qpid-jms")

@test
def pair_vertx_proton_to_qpid_proton_c():
    _test_pair("vertx-proton", "qpid-proton-c")

@test
def pair_vertx_proton_to_qpid_proton_cpp():
    _test_pair("vertx-proton", "qpid-proton-cpp")

@test
def pair_vertx_proton_to_qpid_proton_python():
    _test_pair("vertx-proton", "qpid-proton-python")

@test
def pair_vertx_proton_to_qpid_protonj2():
    _test_pair("vertx-proton", "qpid-protonj2")

@test
def pair_vertx_proton_to_qpid_proton_dotnet():
    _test_pair("vertx-proton", "qpid-proton-dotnet")

@test
def pair_vertx_proton_to_rhea():
    _test_pair("vertx-proton", "rhea")

@test
def pair_vertx_proton_to_vertx_proton():
    _test_pair("vertx-proton", "vertx-proton")

# Bench

@test
def bench():
    with working_dir() as output:
        command = [
            "quiver-bench",
            "--count", "1",
            "--include-servers", "builtin",
            "--include-senders", "qpid-proton-c",
            "--include-receivers", "qpid-proton-c",
            "--verbose",
            "--output", output,
        ]

        run(command)

# TLS/SASL

@test
def anonymous_tls():
    skip_test("Certificate verify fails: https://github.com/ssorj/quiver/issues/70")

    extra_server_args = []
    extra_server_args.append("--key={}".format(TSERVER_PRIVATE_KEY_PEM))
    extra_server_args.append("--key-password={}".format("password"))
    extra_server_args.append("--cert={}".format(TSERVER_CERTIFICATE_PEM))

    with _TestServer(extra_server_args=extra_server_args, scheme="amqps") as server:
        for impl in AMQP_ARROW_IMPLS:
            if not impl_available(impl):
                continue

            run(f"quiver-arrow send {server.url} --impl {impl} --count 1 --verbose")
            run(f"quiver-arrow receive {server.url} --impl {impl} --count 1 --verbose")

@test
def clientauth_tls():
    skip_test("Certificate verify fails: https://github.com/ssorj/quiver/issues/70")

    extra_server_args = []
    extra_server_args.append("--key={}".format(TSERVER_PRIVATE_KEY_PEM))
    extra_server_args.append("--key-password={}".format("password"))
    extra_server_args.append("--cert={}".format(TSERVER_CERTIFICATE_PEM))
    extra_server_args.append("--trusted-db={}".format(TCLIENT_CERTIFICATE_PEM))

    with _TestServer(extra_server_args=extra_server_args, scheme="amqps") as server:
        for impl in AMQP_ARROW_IMPLS:
            if not impl_available(impl):
                continue

            if impl == "qpid-protonj2":
                # XXX Currently failing.  Deferring.
                continue

            cert = TCLIENT_CERTIFICATE_PEM
            key = TCLIENT_PRIVATE_KEY_PEM

            run(f"quiver-arrow send {server.url} --impl {impl} --count 1 --verbose --cert {cert} --key {key}")
            run(f"quiver-arrow receive {server.url} --impl {impl} --count 1 --verbose --cert {cert} --key {key}")

@test
def sasl():
    skip_test("Failure to authenticate using SASL PLAIN: https://github.com/ssorj/quiver/issues/75")

    sasl_user = "myuser"
    sasl_password = "mypassword"

    extra_server_args = []
    extra_server_args.append("--key={}".format(TSERVER_PRIVATE_KEY_PEM))
    extra_server_args.append("--key-password={}".format("password"))
    extra_server_args.append("--cert={}".format(TSERVER_CERTIFICATE_PEM))
    extra_server_args.append("--sasl-user={}".format(sasl_user))
    extra_server_args.append("--sasl-password={}".format(sasl_password))

    with _TestServer(extra_server_args=extra_server_args, scheme="amqp") as server:
        server_url = _urlparse(server.url)
        client_url = "{}://{}:{}@{}{}".format(server_url.scheme,
                                               sasl_user, sasl_password,
                                               server_url.netloc, server_url.path)

        for impl in AMQP_ARROW_IMPLS:
            if not impl_available(impl):
                continue

            run(f"quiver-arrow send {client_url} --impl {impl} --count 1 --verbose")
            run(f"quiver-arrow receive {client_url} --impl {impl} --count 1 --verbose")

class _TestServer:
    def __init__(self, impl="builtin", scheme=None, extra_server_args=[], **kwargs):
        port = get_random_port()

        if impl == "activemq":
            port = "5672"

        self.url = "{}//localhost:{}/q0".format(scheme + ":" if scheme else "", port)
        self.ready_file = make_temp_file()

        command = [
            "quiver-server", self.url,
            "--verbose",
            "--ready-file", self.ready_file,
            "--impl", impl,
        ]

        command.extend(extra_server_args)

        self.proc = start(command, **kwargs)
        self.proc.url = self.url

    def __enter__(self):
        for i in range(30):
            if read(self.ready_file) == "ready\n":
                break

            sleep(0.2)

        return self.proc

    def __exit__(self, exc_type, exc_value, traceback):
        stop(self.proc)
        remove(self.ready_file)

def _test_url():
    return "//localhost:{}/q0".format(get_random_port())

def _test_command(command):
    run(f"{command} --help")
    run(f"{command} --version")

def _test_arrow(impl):
    if not impl_available(impl):
        raise PlanoTestSkipped(f"Arrow '{impl}' is unavailable")

    run(f"quiver-arrow --impl {impl} --info")

    if impl in AMQP_ARROW_IMPLS:
        with _TestServer() as server:
            run(f"quiver-arrow send {server.url} --impl {impl} --count 1 --duration 0 --verbose")
            run(f"quiver-arrow receive {server.url} --impl {impl} --count 1 --duration 0 --verbose")

            # Proton C++ timer trouble: https://github.com/ssorj/quiver/issues/51
            if impl != "qpid-proton-cpp":
                run(f"quiver-arrow send {server.url} --impl {impl} --duration 1 --rate 100 --verbose")
                run(f"quiver-arrow receive {server.url} --impl {impl} --duration 1 --rate 100 --verbose")

            run(f"quiver {server.url} --impl {impl} --duration 1 --body-size 1 --credit 1 --durable --set-message-id")

def _test_server(impl):
    if not impl_available(impl):
        raise PlanoTestSkipped("Server '{}' is unavailable".format(impl))

    run(f"quiver-server --impl {impl} --info")

    with _TestServer(impl=impl) as server:
        run(f"quiver {server.url} --count 1")

def _test_pair(sender_impl, receiver_impl):
    if not impl_available(sender_impl):
        raise PlanoTestSkipped(f"Sender '{sender_impl}' is unavailable")

    if not impl_available(receiver_impl):
        raise PlanoTestSkipped(f"Receiver '{receiver_impl}' is unavailable")

    if receiver_impl in PEER_TO_PEER_ARROW_IMPLS:
        run(f"quiver --sender {sender_impl} --receiver {receiver_impl} --count 1 --duration 0 --verbose")

    with _TestServer() as server:
        run(f"quiver --sender {sender_impl} --receiver {receiver_impl} --count 1 --duration 0 --verbose {server.url}")
