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

#include <chrono>
#include <iostream>
#include <sstream>

using namespace qpid::messaging;
using namespace qpid::types;

static const std::string LINK_OPTIONS =
    "{link: {durable: False, reliability: at-least-once}}";

long now() {
    return std::chrono::duration_cast<std::chrono::milliseconds>
        (std::chrono::system_clock::now().time_since_epoch()).count();
}

void eprint(std::string message) {
    std::cerr << "quiver-arrow: error: " << message << std::endl;
}

struct Client {
    std::string operation;
    std::string id;
    std::string host;
    std::string port;
    std::string path;
    int messages;
    int body_size;
    int credit_window;
    int transaction_size;

    int sent = 0;
    int received = 0;

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

    // XXX This didn't have any effect
    //conn.setOption("container_id", id);

    conn.open();

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
    } catch (const std::exception& e) {
        conn.close();
        throw;
    }
}

void Client::sendMessages(Session& session) {
    Sender sender = session.createSender(path + "; " + LINK_OPTIONS);
    sender.setCapacity(credit_window);

    std::string body(body_size, 'x');

    while (sent < messages) {
        std::string id = std::to_string(sent + 1);
        long stime = now();

        Message message(body);
        message.setMessageId(id);
        message.setProperty("SendTime", Variant(stime));

        sender.send(message);
        sent++;

        std::cout << id << "," << stime << "\n";

        if (transaction_size > 0 && (sent % transaction_size) == 0) {
            session.commit();
        }
    }
}

void Client::receiveMessages(Session& session) {
    Receiver receiver = session.createReceiver(path + "; " + LINK_OPTIONS);
    receiver.setCapacity(credit_window);

    Message message;

    while (received < messages) {
        if (receiver.getAvailable() == 0) {
            continue;
        }

        receiver.get(message);
        received++;
        session.acknowledge();

        std::string id = message.getMessageId();
        long stime = message.getProperties()["SendTime"];
        long rtime = now();

        std::cout << id << "," << stime << "," << rtime << "\n";

        if (transaction_size > 0 && (received % transaction_size) == 0) {
            session.commit();
        }
    }
}

int main(int argc, char** argv) {
    if (argc == 1) {
        std::cout << "Qpid Messaging C++ XXX" << std::endl;
        return 0;
    }

    std::string connection_mode = argv[1];
    std::string channel_mode = argv[2];

    if (connection_mode != "client") {
        eprint("This impl supports client mode only");
        return 1;
    }

    if (channel_mode != "active") {
        eprint("This impl supports active mode only");
        return 1;
    }

    Client client;

    client.operation = argv[3];
    client.id = argv[4];
    client.host = argv[5];
    client.port = argv[6];
    client.path = argv[7];
    client.messages = std::atoi(argv[8]);
    client.body_size = std::atoi(argv[9]);
    client.credit_window = std::atoi(argv[10]);
    client.transaction_size = std::atoi(argv[11]);

    try {
        client.run();
    } catch (const std::exception& e) {
        eprint(e.what());
        return 1;
    }

    return 0;
}
