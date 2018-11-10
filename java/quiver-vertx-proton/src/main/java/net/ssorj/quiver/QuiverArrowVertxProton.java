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
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicInteger;

import org.apache.qpid.proton.amqp.Binary;
import org.apache.qpid.proton.amqp.UnsignedLong;
import org.apache.qpid.proton.amqp.messaging.Accepted;
import org.apache.qpid.proton.amqp.messaging.ApplicationProperties;
import org.apache.qpid.proton.amqp.messaging.Data;
import org.apache.qpid.proton.message.Message;

import io.vertx.core.Handler;
import io.vertx.core.Vertx;
import io.vertx.core.VertxOptions;
import io.vertx.proton.ProtonClient;
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
        final String connectionMode = args[0];
        final String channelMode = args[1];
        final String operation = args[2];
        final String id = args[3];
        final String host = args[4];
        final int port = Integer.parseInt(args[5]);
        final String path = args[6];
        final int desiredDuration = Integer.parseInt(args[7]);
        final int desiredCount = Integer.parseInt(args[8]);
        final int bodySize = Integer.parseInt(args[9]);
        final int creditWindow = Integer.parseInt(args[10]);
        final int transactionSize = Integer.parseInt(args[11]);
        final String[] flags = args[12].split(",");

        final boolean durable = Arrays.asList(flags).contains("durable");

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

        client.connect(host, port, (res) -> {
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
                        send(connection, path, desiredCount, bodySize, durable);
                    } else {
                        receive(connection, path, desiredCount, creditWindow);
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
                             final int desiredCount, final int bodySize, final boolean durable) {
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
                            final String id = String.valueOf(count.get());
                            final long stime = System.currentTimeMillis();
                            final Map<String, Object> props = new HashMap<>();

                            props.put("SendTime", stime);

                            msg.setMessageId(id);
                            msg.setBody(new Data(new Binary(body)));
                            msg.setApplicationProperties(new ApplicationProperties(props));

                            if (durable) {
                                msg.setDurable(true);
                            }

                            sender.send(msg);
                            count.incrementAndGet();

                            line.setLength(0);
                            out.append(line.append(id).append(',').append(stime).append('\n'));
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
                                final int desiredCount, final int creditWindow) {
        final StringBuilder line = new StringBuilder();
        final BufferedWriter out = getWriter();
        final AtomicInteger count = new AtomicInteger(0);
        final int creditTopUpThreshold = Math.max(1, creditWindow / 2);
        final ProtonReceiver receiver = connection.createReceiver(address);

        receiver.setAutoAccept(false).setPrefetch(0).flow(creditWindow);
        receiver.handler((delivery, msg) -> {
                try {
                    try {
                        final Object id = msg.getMessageId();
                        final long stime = (Long) msg.getApplicationProperties().getValue().get("SendTime");
                        final long rtime = System.currentTimeMillis();

                        line.setLength(0);
                        out.append(line.append(id).append(',').append(stime).append(',').append(rtime).append('\n'));

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
