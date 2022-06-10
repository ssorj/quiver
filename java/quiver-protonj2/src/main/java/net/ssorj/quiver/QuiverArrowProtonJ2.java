/*
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
 */
package net.ssorj.quiver;

import java.io.BufferedWriter;
import java.io.IOException;
import java.io.OutputStreamWriter;
import java.util.Arrays;
import java.util.HashMap;
import java.util.Timer;
import java.util.TimerTask;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

import org.apache.qpid.protonj2.client.Client;
import org.apache.qpid.protonj2.client.ClientOptions;
import org.apache.qpid.protonj2.client.Connection;
import org.apache.qpid.protonj2.client.ConnectionOptions;
import org.apache.qpid.protonj2.client.Delivery;
import org.apache.qpid.protonj2.client.Message;
import org.apache.qpid.protonj2.client.Receiver;
import org.apache.qpid.protonj2.client.ReceiverOptions;
import org.apache.qpid.protonj2.client.Sender;
import org.apache.qpid.protonj2.client.SenderOptions;
import org.apache.qpid.protonj2.client.Tracker;
import org.apache.qpid.protonj2.client.exceptions.ClientException;
import org.apache.qpid.protonj2.types.UnsignedLong;

public class QuiverArrowProtonJ2 {

    private static final String CLIENT = "client";
    private static final String ACTIVE = "active";
    private static final String RECEIVE = "receive";
    private static final String SEND = "send";

    private enum Role {
        SENDER,
        RECEIVER
    }

    public static void main(final String[] args) {
        try {
            doMain(args);
        } catch (Exception e) {
            e.printStackTrace();
            System.exit(1);
        }
    }

    private static void doMain(final String[] args) throws Exception {
        final HashMap<String, String> kwargs = new HashMap<>();

        for (String arg : args) {
            final String[] elems = arg.split("=", 2);
            kwargs.put(elems[0], elems[1]);
        }

        final String connectionMode = kwargs.get("connection-mode");
        final String channelMode = kwargs.get("channel-mode");
        final String operation = kwargs.get("operation");
        final String id = kwargs.get("id");
        final String scheme = kwargs.get("scheme");
        final String host = kwargs.get("host");
        final int port = Integer.parseInt(kwargs.get("port"));
        final String address = kwargs.get("path");
        final String username = kwargs.get("username");
        final String password = kwargs.get("password");
        final String cert = kwargs.get("cert");
        final String key = kwargs.get("key");
        final int desiredDuration = Integer.parseInt(kwargs.get("duration"));
        final int desiredCount = Integer.parseInt(kwargs.get("count"));
        final int bodySize = Integer.parseInt(kwargs.get("body-size"));
        final int creditWindow = Integer.parseInt(kwargs.get("credit-window"));
        final int transactionSize = Integer.parseInt(kwargs.get("transaction-size"));
        final boolean durable = Integer.parseInt(kwargs.get("durable")) == 1;

        if (!CLIENT.equalsIgnoreCase(connectionMode)) {
            throw new RuntimeException("This impl currently supports client mode only");
        }

        if (!ACTIVE.equalsIgnoreCase(channelMode)) {
            throw new RuntimeException("This impl currently supports active mode only");
        }

        if (transactionSize > 0) {
            throw new RuntimeException("This impl doesn't support transactions");
        }

        final Role role;

        if (SEND.equalsIgnoreCase(operation)) {
            role = Role.SENDER;
        } else if (RECEIVE.equalsIgnoreCase(operation)) {
            role = Role.RECEIVER;
        } else {
            throw new IllegalStateException("Unknown operation: " + operation);
        }

        final Client client = Client.create(new ClientOptions().id(id));
        final ConnectionOptions options = new ConnectionOptions();

        options.user(username);
        options.password(password);

        if ("amqps".equals(scheme)) {
            options.sslEnabled(true).sslOptions().trustAll(true).verifyHost(false);

            if (cert != null && key != null) {
                // TODO - options.setPemKeyCertOptions(new PemKeyCertOptions().setCertPath(cert).setKeyPath(key));
            }
        }

        final Arrow arrow = new Arrow(client, options, host, port,
                                      address, role, creditWindow,
                                      desiredDuration, desiredCount,
                                      bodySize, transactionSize, durable);

        arrow.run();
    }

    static class Arrow {

        private final Client client;
        private final ConnectionOptions options;
        private Role role;
        private String host;
        private int port;
        private String address;
        private int desiredDuration;
        private int desiredCount;
        private int prefecth;
        private int bodySize;
        private int transactionSize;
        private boolean durable;

        // Runtime data collected for Quiver results
        protected int sent;
        protected int received;
        protected final AtomicBoolean stopping = new AtomicBoolean();

        Arrow(final Client client, final ConnectionOptions options, final String host, final int port,
              final String address, final Role role, final int prefetch,
              final int desiredDuration, final int desiredCount, final int bodySize,
              final int transactionSize, final boolean durable) {

            this.client = client;
            this.options = options;
            this.host = host;
            this.port = port;
            this.address = address;
            this.role = role;
            this.prefecth = prefetch;
            this.desiredDuration = desiredDuration;
            this.desiredCount = desiredCount;
            this.bodySize = bodySize;
            this.transactionSize = transactionSize;
            this.durable = durable;
        }

        void run() {
            try {
                final Connection connection = client.connect(host, port, options);

                if (desiredDuration > 0) {
                    final Timer timer = new Timer(true);
                    final TimerTask task = new TimerTask() {
                            public void run() {
                                stopping.lazySet(true);
                            }
                        };

                    timer.schedule(task, desiredDuration * 1000);
                }

                try {
                    switch (role) {
                        case RECEIVER:
                            receiveMessages(connection);
                            break;
                        case SENDER:
                            sendMessages(connection);
                            break;
                    }
                } catch (ClientException | IOException e) {
                    // Ignore error from remote close
                    return;
                }

                connection.close();
            } catch (ClientException e) {
                throw new RuntimeException(e);
            }
        }

        private BufferedWriter getWriter() {
            return new BufferedWriter(new OutputStreamWriter(System.out));
        }

        void sendMessages(final Connection connection) throws IOException, ClientException {
            final StringBuilder line = new StringBuilder();
            final BufferedWriter out = getWriter();
            final SenderOptions senderOptions = new SenderOptions();
            senderOptions.targetOptions().capabilities("queue");

            final Sender sender = connection.openSender(address, senderOptions);
            final byte[] body = new byte[bodySize];

            Arrays.fill(body, (byte) 120);

            Tracker lastSentTracker = null;

            if (transactionSize > 0) {
                sender.session().beginTransaction();
            }

            while (!stopping.get()) {
                final Message<byte[]> message = Message.create(body);
                final long stime = System.currentTimeMillis();

                message.property("SendTime", stime);
                message.messageId(String.valueOf(sent));
                if (durable) {
                    message.durable(true);
                }

                lastSentTracker = sender.send(message);
                sent += 1;

                line.setLength(0);
                out.append(line.append(message.messageId()).append(',').append(stime).append('\n'));

                if (transactionSize > 0 && (sent % transactionSize) == 0) {
                    sender.session().commitTransaction();
                    sender.session().beginTransaction();
                }

                if (sent == desiredCount) {
                    break;
                }
            }

            try {
                lastSentTracker.awaitSettlement();
            } catch (ClientException e) {
                e.printStackTrace();
                throw new IOException(e);
            }

            if (transactionSize > 0) {
                sender.session().commitTransaction();
            }

            out.flush();
        }

        void receiveMessages(final Connection connection) throws ClientException, IOException {
            final StringBuilder line = new StringBuilder();
            final BufferedWriter out = getWriter();
            final ReceiverOptions receiverOptions = new ReceiverOptions();
            receiverOptions.sourceOptions().capabilities("queue");
            receiverOptions.creditWindow(prefecth);
            final Receiver receiver = connection.openReceiver(address, receiverOptions);

            if (transactionSize > 0) {
                receiver.session().beginTransaction();
            }

            while (!stopping.get()) {
                final Delivery delivery = receiver.receive(100, TimeUnit.MILLISECONDS);

                if (delivery == null) {
                    continue;
                }

                Message<byte[]> message = delivery.message();

                received += 1;

                final Object id = message.messageId();
                final long stime = (long) message.property("SendTime");
                final long rtime = System.currentTimeMillis();

                line.setLength(0);
                out.append(line.append(id).append(',').append(stime).append(',').append(rtime).append('\n'));

                if (transactionSize > 0 && (received % transactionSize) == 0) {
                    receiver.session().commitTransaction();
                    receiver.session().beginTransaction();
                }

                if (received == desiredCount) {
                    break;
                }
            }

            if (transactionSize > 0) {
                receiver.session().commitTransaction();
            }

            out.flush();
        }
    }
}
