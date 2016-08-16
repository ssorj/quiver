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

using namespace qpid::messaging;

int main(int argc, char** argv) {
    int nconnections = std::atoi(argv[1]);
    int nsessions = std::atoi(argv[2]);
    int nlinks = std::atoi(argv[3]);
    int nmessages = std::atoi(argv[4]);
    int nbytes = std::atoi(argv[5]);

    std::string host = "localhost:5672";
    std::string address = "test";

    std::cerr << nconnections << std::endl;
    std::cerr << nsessions << std::endl;
    std::cerr << nlinks << std::endl;
    std::cerr << nmessages << std::endl;
    std::cerr << nbytes << std::endl;

    Connection connections[nconnections];
    Session sessions[nsessions];
    Sender links[nlinks];
    Message messages[nmessages];

    std::printf("Creating %i connections\n", nconnections);

    for (int i = 0; i < nconnections; i++) {
        connections[i] = Connection(host);
    }

    std::printf("Opening connections\n");

    for (Connection conn : connections) {
        conn.open();
    }

    std::printf("Creating %i sessions\n", nsessions);

    for (int i = 0; i < nsessions; i++) {
        Connection conn = connections[i % nconnections];
        sessions[i] = conn.createSession();
    }

    Connection connection = Connection(host);

    try {
        connection.open();

        Session session = connection.createSession(address);
        Receiver receiver = session.createReceiver(address);
        Sender sender = session.createSender(address);

        sender.send(Message("Hello world!"));

        Message message = receiver.fetch(Duration::SECOND * 1);
        std::cout << message.getContent() << std::endl;
        session.acknowledge();

        connection.close();

        return 0;
    } catch(const std::exception& error) {
        std::cerr << error.what() << std::endl;
        return 1;
    }
}
