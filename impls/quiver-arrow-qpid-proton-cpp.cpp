/*
 *
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 *
 */

#include <proton/connection.hpp>
#include <proton/connection_options.hpp>
#include <proton/container.hpp>
#include <proton/default_container.hpp>
#include <proton/delivery.hpp>
#include <proton/duration.hpp>
#include <proton/link.hpp>
#include <proton/listener.hpp>
#include <proton/message.hpp>
#include <proton/message_id.hpp>
#include <proton/messaging_handler.hpp>
#include <proton/receiver_options.hpp>
#include <proton/target_options.hpp>
#include <proton/tracker.hpp>
#include <proton/transfer.hpp>
#include <proton/transport.hpp>
#include <proton/value.hpp>
#include <proton/version.h>
#include <proton/work_queue.hpp>

#include <algorithm>
#include <assert.h>
#include <chrono>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

int64_t now() {
    return std::chrono::duration_cast<std::chrono::milliseconds>
        (std::chrono::system_clock::now().time_since_epoch()).count();
}

void eprint(std::string message) {
    std::cerr << "quiver-arrow: error: " << message << std::endl;
}

std::vector<std::string> split(const std::string &s, char delim) {
    std::stringstream ss;
    std::string elem;
    std::vector<std::string> elems;

    ss.str(s);

    while (std::getline(ss, elem, delim)) {
        elems.push_back(elem);
    }

    return elems;
}

struct handler : public proton::messaging_handler {
    std::string connection_mode;
    std::string channel_mode;
    std::string operation;
    std::string id;
    std::string host;
    std::string port;
    std::string path;
    int desired_duration;
    int desired_count;
    int body_size;
    int credit_window;
    bool durable;

    proton::connection connection;
    proton::listener listener;
    proton::binary body;

    long start_time = 0;
    int sent = 0;
    int received = 0;
    int accepted = 0;

    void on_container_start(proton::container& cont) override {
        body = std::string(body_size, 'x');

        std::string domain = host + ":" + port;
        proton::connection_options opts;

        opts.sasl_allowed_mechs("ANONYMOUS");

        if (connection_mode == "client") {
            connection = cont.connect(domain, opts);
        } else if (connection_mode == "server") {
            listener = cont.listen(domain, opts);
        } else {
            throw std::exception();
        }

        start_time = now();

        if (desired_duration > 0) {
            cont.schedule(desired_duration * proton::duration::SECOND, [this] { stop(); });
        }
    }

    void on_connection_open(proton::connection& conn) override {
        if (channel_mode == "active") {
            if (operation == "send") {
                conn.open_sender(path);
            } else if (operation == "receive") {
                proton::receiver_options opts;
                opts.credit_window(credit_window);

                conn.open_receiver(path, opts);
            } else {
                throw std::exception();
            }
        } else if (channel_mode == "passive") {
            connection = conn;
            connection.open();
        } else {
            throw new std::exception();
        }
    }

    void on_receiver_open(proton::receiver& rcv) override {
        proton::receiver_options ropts;
        proton::target_options topts;

        topts.address(rcv.target().address());

        ropts.credit_window(credit_window);
        ropts.target(topts);

        rcv.open(ropts);
    }

    void on_sendable(proton::sender& snd) override {
        assert (operation == "send");

        proton::message msg;

        while (snd.credit() > 0) {
            if (desired_count > 0 && sent == desired_count) {
                break;
            }

            std::string id = std::to_string(sent + 1);
            int64_t stime = now();

            msg.clear();
            msg.body(body);
            msg.id(id);
            msg.properties().put("SendTime", stime);

            if (durable) {
                msg.durable(true);
            }

            snd.send(msg);
            sent++;

            std::cout << id << "," << stime << "\n";
        }
    }

    void on_tracker_accept(proton::tracker& trk) override {
        accepted++;

        if (accepted == desired_count) {
            stop();
        }
    }

    void on_message(proton::delivery& dlv, proton::message& msg) override {
        assert (operation == "receive");

        received++;

        proton::message_id id = msg.id();
        proton::scalar stime = msg.properties().get("SendTime");
        int64_t rtime = now();

        std::cout << id << "," << stime << "," << rtime << "\n";

        if (received == desired_count) {
            stop();
        }
    }

    void stop() {
        if (!!connection) {
            connection.close();
        }

        if (connection_mode == "server") {
            listener.stop();
        }
    }

    void on_transport_error(proton::transport& trans) override {
        // On server ignore errors from dummy connections to see if we are listening.
        if (connection_mode == "client") {
            on_error(trans.error());
        }
    }
};

int main(int argc, char** argv) {
    if (argc == 1) {
        std::cout << "Qpid Proton C++ "
                  << PN_VERSION_MAJOR << "."
                  << PN_VERSION_MINOR << "."
                  << PN_VERSION_POINT << std::endl;
        return 0;
    }

    int transaction_size = std::atoi(argv[12]);

    if (transaction_size > 0) {
        eprint("This impl doesn't support transactions");
        return 1;
    }

    handler h;

    h.connection_mode = argv[1];
    h.channel_mode = argv[2];
    h.operation = argv[3];
    h.id = argv[4];
    h.host = argv[5];
    h.port = argv[6];
    h.path = argv[7];

    h.desired_duration = std::atoi(argv[8]);
    h.desired_count = std::atoi(argv[9]);
    h.body_size = std::atoi(argv[10]);
    h.credit_window = std::atoi(argv[11]);

    std::vector<std::string> flags = split(argv[13], ',');

    h.durable = std::any_of(flags.begin(), flags.end(), [](std::string &s) { return s == "durable"; });

    try {
        proton::default_container(h, h.id).run();
    } catch (const std::exception& e) {
        eprint(e.what());
        return 1;
    }

    return 0;
}
