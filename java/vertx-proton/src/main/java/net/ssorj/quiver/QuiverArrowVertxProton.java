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
import java.io.OutputStreamWriter;
import java.io.PrintWriter;
import java.util.Arrays;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;

import org.apache.qpid.proton.amqp.Binary;
import org.apache.qpid.proton.amqp.UnsignedLong;
import org.apache.qpid.proton.amqp.messaging.Accepted;
import org.apache.qpid.proton.amqp.messaging.ApplicationProperties;
import org.apache.qpid.proton.amqp.messaging.Data;
import org.apache.qpid.proton.message.Message;

import io.vertx.core.Vertx;
import io.vertx.proton.ProtonClient;
import io.vertx.proton.ProtonConnection;
import io.vertx.proton.ProtonReceiver;
import io.vertx.proton.ProtonSender;

public class QuiverArrowVertxProton {
    private static final int DEFAULT_AMQP_PORT = 5672;

    private static final String CLIENT = "client";
    private static final String ACTIVE = "active";
    private static final String RECEIVE = "receive";
    private static final String SEND = "send";

    private static final Accepted ACCEPTED = Accepted.getInstance();

    public static void main(String[] args) {
        try {
            doMain(args);
        } catch (Exception e) {
            e.printStackTrace();
            System.exit(1);
        }
    }
    
    public static void doMain(String[] args) throws Exception {
        String connectionMode = args[0];
        String channelMode = args[1];
        String operation = args[2];
        String id = args[3];
        String host = args[4];
        String port = args[5];
        String path = args[6];
        int messages = Integer.parseInt(args[7]);
        int bodySize = Integer.parseInt(args[8]);
        int creditWindow = Integer.parseInt(args[9]);

        if (!CLIENT.equalsIgnoreCase(connectionMode)) {
            throw new RuntimeException("This impl currently supports client mode only");
        }

        if (!ACTIVE.equalsIgnoreCase(channelMode)) {
            throw new RuntimeException("This impl currently supports active mode only");
        }

        final boolean sender;
        
        if (SEND.equalsIgnoreCase(operation)) {
            sender = true;
        } else if (RECEIVE.equalsIgnoreCase(operation)) {
            sender = false;
        } else {
            throw new java.lang.IllegalStateException("Unknown operation: " + operation);
        }

        final int portNumber;
        
        if (port.equals("-")) {
            portNumber = DEFAULT_AMQP_PORT;
        } else {
            portNumber = Integer.parseInt(port);
        }
        
        CountDownLatch completionLatch = new CountDownLatch(1);
        Vertx vertx = Vertx.vertx();
        ProtonClient client = ProtonClient.create(vertx);
        
        client.connect(host, portNumber, res -> {
                if (res.succeeded()) {
                    ProtonConnection connection = res.result();
                    connection.setContainer(id);

                    if (sender) {
                        send(connection, path, messages, bodySize, completionLatch);
                    } else {
                        receive(connection, path, messages, creditWindow, completionLatch);
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

    // TODO: adjust? The writer is [needlessly] synchronizing every
    // write, the buffer may flush more/less often than desired?.
    private static PrintWriter getOutputWriter() {
        return new PrintWriter(new BufferedWriter(new OutputStreamWriter(System.out)));
    }

    private static void send(ProtonConnection connection, String address,
                             int messages, int bodySize, CountDownLatch latch) {
        connection.open();

        byte[] body = new byte[bodySize];
        Arrays.fill(body, (byte) 120);
        PrintWriter out = getOutputWriter();
        AtomicLong count = new AtomicLong(1);
        ProtonSender sender = connection.createSender(address);
        
        sender.sendQueueDrainHandler(s -> {
                while (!sender.sendQueueFull() && count.get() <= messages) {
                    Message msg = Message.Factory.create();

                    UnsignedLong id = UnsignedLong.valueOf(count.get());
                    msg.setMessageId(id);

                    msg.setBody(new Data(new Binary(body)));

                    Map<String, Object> props = new HashMap<>();
                    msg.setApplicationProperties(new ApplicationProperties(props));
                    long stime = System.currentTimeMillis();
                    props.put("SendTime", stime);

                    sender.send(msg);

                    out.printf("%s,%d\n", id, stime);

                    if (count.getAndIncrement() >= messages) {
                        out.flush();
          
                        connection.closeHandler(x -> {
                                latch.countDown();
                            });
                        connection.close();
                    };
                }
            });
        sender.open();
    }

    private static void receive(ProtonConnection connection, String address,
                                int messages, int creditWindow, CountDownLatch latch) {
        connection.open();

        PrintWriter out = getOutputWriter();
        AtomicInteger count = new AtomicInteger(1);
        ProtonReceiver receiver = connection.createReceiver(address);

        receiver.setAutoAccept(false).setPrefetch(0).flow(creditWindow);
        receiver.handler((delivery, msg) -> {
                Object id = msg.getMessageId();
                long stime = (Long) msg.getApplicationProperties().getValue().get("SendTime");
                long rtime = System.currentTimeMillis();

                out.printf("%s,%d,%d\n", id, stime, rtime);

                delivery.disposition(ACCEPTED, true);
                receiver.flow(1);

                if (count.getAndIncrement() >= messages) {
                    out.flush();

                    connection.closeHandler(x -> {
                            latch.countDown();
                        });
                    connection.close();
                }
            }).open();
    }
}
