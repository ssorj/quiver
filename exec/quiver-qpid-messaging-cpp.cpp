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

#include <iostream>
#include <chrono>

using namespace qpid::messaging;
using namespace qpid::types;
using namespace std::chrono;

static const std::string CONNECTION_OPTIONS =
    "{protocol: amqp1.0, sasl_mechanisms: ANONYMOUS}";
static const std::string LINK_OPTIONS =
    "{link: {durable: True, reliability: at-least-once}}";

long now() {
    return duration_cast<milliseconds>
        (system_clock::now().time_since_epoch()).count();
}

struct Client {
    std::string output_dir;
    std::string domain;
    std::string path;
    std::string operation;
    int messages;
    int bytes;
    int credit;

    int sent = 0;
    int received = 0;

    void run();
    void sendMessages(Session&);
    void receiveMessages(Session&);
};

void Client::run() {
    Connection conn(domain, CONNECTION_OPTIONS);
    conn.open();

    try {
        Session session = conn.createSession();

        if (operation == "send") {
            sendMessages(session);
        } else if (operation == "receive") {
            receiveMessages(session);
        } else {
            throw std::exception();
        }
    } catch (const std::exception& e) {
        conn.close();
        throw;
    }
}

void Client::sendMessages(Session& session) {
    Sender sender = session.createSender(path + "; " + LINK_OPTIONS);
    sender.setCapacity(credit);

    std::string body(bytes, 'x');
    
    while (sent < messages) {
        std::string id = std::to_string(sent + 1);
        long stime = now();
        
        Message message(body);
        message.setMessageId(id);
        message.setProperty("SendTime", Variant(stime));

        sender.send(message);
            
        std::cout << id << "," << stime << "\n";
        
        sent++;
    }

    // XXX flush?
}

void Client::receiveMessages(Session& session) {
    Receiver receiver = session.createReceiver(path + "; " + LINK_OPTIONS);
    receiver.setCapacity(credit);

    Message message;

    while (received < messages) {
        if (receiver.getAvailable() == 0) {
            continue;
        }

        receiver.get(message);
        session.acknowledge();

        std::string id = message.getMessageId();
        long stime = message.getProperties()["SendTime"];
        long rtime = now();

        std::cout << id << "," << stime << "," << rtime << "\n";
        
        received++;
    }

    // XXX flush?
}

int main(int argc, char** argv) {
    std::string mode = argv[2];

    Client client;
    client.output_dir = argv[1];
    client.domain = argv[3];
    client.path = argv[4];
    client.operation = argv[5];
    client.messages = std::atoi(argv[6]);
    client.bytes = std::atoi(argv[7]);
    client.credit = std::atoi(argv[8]);

    try {
        client.run();
    } catch (const std::exception& e) {
        std::cerr << e.what() << std::endl;
        return 1;
    }

    return 0;
}
