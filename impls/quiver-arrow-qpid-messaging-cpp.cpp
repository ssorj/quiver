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

#include <qpid/messaging/Connection.h>
#include <qpid/messaging/Message.h>
#include <qpid/messaging/Receiver.h>
#include <qpid/messaging/Sender.h>
#include <qpid/messaging/Session.h>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <iostream>
#include <map>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

using namespace qpid::messaging;
using namespace qpid::types;

static const std::string LINK_OPTIONS =
    "{link: {durable: False, reliability: at-least-once}}";

int64_t now() {
    return std::chrono::duration_cast<std::chrono::milliseconds>
        (std::chrono::system_clock::now().time_since_epoch()).count();
}

void eprint(std::string message) {
    std::cerr << "quiver-arrow: error: " << message << std::endl;
}

std::vector<std::string> split(const std::string& s, char delim, int max) {
    std::stringstream ss;
    std::string elem;
    std::vector<std::string> elems;

    ss.str(s);

    for (int i = 0; std::getline(ss, elem, delim); i++) {
        elems.push_back(elem);
        if (max != 0 && i == max) break;
    }

    return elems;
}

struct Client {
    std::string operation;
    std::string id;
    std::string host;
    std::string port;
    std::string path;
    std::chrono::seconds desired_duration;
    int desired_count;
    int body_size;
    int credit_window;
    int transaction_size;
    bool durable;

    int64_t start_time;
    int sent = 0;
    int received = 0;
    std::atomic<bool> stopping {false};

    void run();
    void sendMessages(Session&);
    void receiveMessages(Session&);
};

void Client::run() {
    std::string domain = host + ":" + port;
    std::ostringstream oss;
    oss << "{"
        << "protocol: amqp1.0,"
        << "container_id: " << id << ","
        << "sasl_mechanisms: ANONYMOUS"
        << "}";
    std::string options = oss.str();

    Connection conn(domain, options);
    conn.open();

    start_time = now();

    if (desired_duration > std::chrono::seconds::zero()) {
        std::thread timer([this]() {
                std::this_thread::sleep_for(desired_duration);
                stopping = true;
            });

        timer.detach();
    }

    try {
        Session session;

        if (transaction_size > 0) {
            session = conn.createTransactionalSession();
        } else {
            session = conn.createSession();
        }

        if (operation == "send") {
            sendMessages(session);
        } else if (operation == "receive") {
            receiveMessages(session);
        } else {
            throw std::exception();
        }

        if (transaction_size > 0) {
            session.commit();
        }

        conn.close();
    } catch (const ConnectionError& e) {
        // Ignore error from remote close
    } catch (const std::exception& e) {
        conn.close();
        throw;
    }
}

void Client::sendMessages(Session& session) {
    Sender sender = session.createSender(path + "; " + LINK_OPTIONS);
    sender.setCapacity(credit_window);

    std::string body(body_size, 'x');

    while (!stopping) {
        std::string id = std::to_string(sent + 1);
        int64_t stime = now();

        Message message(body);
        message.setMessageId(id);
        message.setProperty("SendTime", Variant(stime));

        if (durable) {
            message.setDurable(true);
        }

        sender.send(message);
        sent++;

        std::cout << id << "," << stime << "\n";

        if (transaction_size > 0 && (sent % transaction_size) == 0) {
            session.commit();
        }

        if (sent == desired_count) {
            break;
        }
    }
}

void Client::receiveMessages(Session& session) {
    Receiver receiver = session.createReceiver(path + "; " + LINK_OPTIONS);
    receiver.setCapacity(credit_window);

    Message message;

    while (!stopping) {
        if (receiver.getAvailable() == 0) {
            continue;
        }

        receiver.get(message);
        received++;

        session.acknowledge();

        std::string id = message.getMessageId();
        int64_t stime = message.getProperties()["SendTime"];
        int64_t rtime = now();

        std::cout << id << "," << stime << "," << rtime << "\n";

        if (transaction_size > 0 && (received % transaction_size) == 0) {
            session.commit();
        }

        if (received == desired_count) {
            break;
        }
    }
}

int main(int argc, char** argv) {
    if (argc == 1) {
        std::cout << "Qpid Messaging C++ XXX" << std::endl;
        return 0;
    }

    std::map<std::string, std::string> kwargs {};

    for (int i = 1; i < argc; i++) {
        auto pair = split(argv[i], '=', 1);
        kwargs[pair[0]] = pair[1];
    }

    std::string connection_mode = kwargs["connection-mode"];
    std::string channel_mode = kwargs["channel-mode"];

    if (connection_mode != "client") {
        eprint("This impl supports client mode only");
        return 1;
    }

    if (channel_mode != "active") {
        eprint("This impl supports active mode only");
        return 1;
    }

    Client client;

    client.operation = kwargs["operation"];
    client.id = kwargs["id"];
    client.host = kwargs["host"];
    client.port = kwargs["port"];
    client.path = kwargs["path"];
    client.desired_duration = std::chrono::seconds(std::stoi(kwargs["duration"]));
    client.desired_count = std::stoi(kwargs["count"]);
    client.body_size = std::stoi(kwargs["body-size"]);
    client.credit_window = std::stoi(kwargs["credit-window"]);
    client.transaction_size = std::stoi(kwargs["transaction-size"]);
    client.durable = std::stoi(kwargs["durable"]);

    try {
        client.run();
    } catch (const std::exception& e) {
        eprint(e.what());
        return 1;
    }

    return 0;
}
