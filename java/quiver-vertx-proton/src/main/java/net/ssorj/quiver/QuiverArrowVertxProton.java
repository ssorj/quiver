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

package net.ssorj.quiver;

import java.io.BufferedWriter;
import java.io.IOException;
import java.io.OutputStreamWriter;
import java.util.Arrays;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicInteger;

import org.apache.qpid.proton.amqp.Binary;
import org.apache.qpid.proton.amqp.messaging.Accepted;
import org.apache.qpid.proton.amqp.messaging.ApplicationProperties;
import org.apache.qpid.proton.amqp.messaging.Data;
import org.apache.qpid.proton.message.Message;

import io.vertx.core.Vertx;
import io.vertx.core.VertxOptions;
import io.vertx.core.net.PemKeyCertOptions;
import io.vertx.proton.ProtonClient;
import io.vertx.proton.ProtonClientOptions;
import io.vertx.proton.ProtonConnection;
import io.vertx.proton.ProtonReceiver;
import io.vertx.proton.ProtonSender;

public class QuiverArrowVertxProton {
    private static final String CLIENT = "client";
    private static final String ACTIVE = "active";
    private static final String RECEIVE = "receive";
    private static final String SEND = "send";

    private static final Accepted ACCEPTED = Accepted.getInstance();

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
        final String path = kwargs.get("path");
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
        final boolean setMessageID = Integer.parseInt(kwargs.get("set-message-id")) == 1;

        if (!CLIENT.equalsIgnoreCase(connectionMode)) {
            throw new RuntimeException("This impl currently supports client mode only");
        }

        if (!ACTIVE.equalsIgnoreCase(channelMode)) {
            throw new RuntimeException("This impl currently supports active mode only");
        }

        if (transactionSize > 0) {
            throw new RuntimeException("This impl doesn't support transactions");
        }

        final boolean sender;

        if (SEND.equalsIgnoreCase(operation)) {
            sender = true;
        } else if (RECEIVE.equalsIgnoreCase(operation)) {
            sender = false;
        } else {
            throw new java.lang.IllegalStateException("Unknown operation: " + operation);
        }

        final CountDownLatch completionLatch = new CountDownLatch(1);
        final Vertx vertx = Vertx.vertx(new VertxOptions().setPreferNativeTransport(true));
        final ProtonClient client = ProtonClient.create(vertx);


        final ProtonClientOptions options = new ProtonClientOptions();

        if ("amqps".equals(scheme)) {
            options.setSsl(true)
                   .setTrustAll(true)
                   .setHostnameVerificationAlgorithm("");

            if (cert != null && key != null) {
                options.setPemKeyCertOptions(new PemKeyCertOptions()
                                                     .setCertPath(cert)
                                                     .setKeyPath(key));
            }
        }

        client.connect(options, host, port, username, password, (res) -> {
                if (res.succeeded()) {
                    final ProtonConnection connection = res.result();

                    connection.setContainer(id);
                    connection.closeHandler(x -> {
                            completionLatch.countDown();
                        });

                    if (desiredDuration > 0) {
                        vertx.setTimer(desiredDuration * 1000, timerId -> {
                                connection.close();
                            });
                    }

                    if (sender) {
                        send(connection, path, desiredCount, bodySize, durable, setMessageID);
                    } else {
                        receive(connection, path, desiredCount, creditWindow, setMessageID);
                    }
                } else {
                    res.cause().printStackTrace();
                    completionLatch.countDown();
                }
            });

        // Await the operations completing, then shut down the Vertx
        // instance.
        completionLatch.await();

        vertx.close();
    }

    private static BufferedWriter getWriter() {
        return new BufferedWriter(new OutputStreamWriter(System.out));
    }

    private static void send(final ProtonConnection connection, final String address,
                             final int desiredCount, final int bodySize, final boolean durable,
                             final boolean setMessageID) {
        final StringBuilder line = new StringBuilder();
        final BufferedWriter out = getWriter();
        final AtomicInteger count = new AtomicInteger(0);
        final ProtonSender sender = connection.createSender(address);
        final byte[] body = new byte[bodySize];

        Arrays.fill(body, (byte) 120);

        sender.sendQueueDrainHandler((s) -> {
                try {
                    try {
                        while (!sender.sendQueueFull()) {
                            int sent = count.get();

                            if (sent > 0 && sent == desiredCount) {
                                connection.close();
                                break;
                            }

                            final Message msg = Message.Factory.create();
                            final Map<String, Object> props = new HashMap<>();

                            msg.setBody(new Data(new Binary(body)));
                            msg.setApplicationProperties(new ApplicationProperties(props));

                            if (durable) {
                                msg.setDurable(true);
                            }

                            if (setMessageID) {
                                final String id = String.valueOf(count.get());
                                msg.setMessageId(id);
                            }

                            final long stime = System.currentTimeMillis();
                            props.put("SendTime", stime);

                            sender.send(msg);
                            count.incrementAndGet();

                            line.setLength(0);
                            out.append(line.append(stime).append(",0\n"));
                        }
                    } finally {
                        out.flush();
                    }
                } catch (IOException e) {
                    throw new RuntimeException(e);
                }
            });

        connection.open();
        sender.open();
    }

    private static void receive(final ProtonConnection connection, final String address,
                                final int desiredCount, final int creditWindow, final boolean setMessageID) {
        final StringBuilder line = new StringBuilder();
        final BufferedWriter out = getWriter();
        final AtomicInteger count = new AtomicInteger(0);
        final int creditTopUpThreshold = Math.max(1, creditWindow / 2);
        final ProtonReceiver receiver = connection.createReceiver(address);

        receiver.setAutoAccept(false).setPrefetch(0).flow(creditWindow);
        receiver.handler((delivery, msg) -> {
                try {
                    try {
                        if (setMessageID) {
                            final Object id = msg.getMessageId();
                        }

                        final long stime = (Long) msg.getApplicationProperties().getValue().get("SendTime");
                        final long rtime = System.currentTimeMillis();

                        line.setLength(0);
                        out.append(line.append(stime).append(',').append(rtime).append('\n'));

                        delivery.disposition(ACCEPTED, true);

                        final int credit = receiver.getCredit();

                        if (credit < creditTopUpThreshold) {
                            receiver.flow(creditWindow - credit);
                        }

                        if (count.incrementAndGet() == desiredCount) {
                            connection.close();
                        }
                    } finally {
                        out.flush();
                    }
                } catch (IOException e) {
                    throw new RuntimeException(e);
                }
            });

        connection.open();
        receiver.open();
    }
}
