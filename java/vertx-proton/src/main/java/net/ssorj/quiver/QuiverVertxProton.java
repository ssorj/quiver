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
import java.net.URI;
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

public class QuiverVertxProton {
    private static final int DEFAULT_AMQP_PORT = 5672;

    private static final String CLIENT = "client";
    private static final String RECEIVE = "receive";
    private static final String SEND = "send";

    private static final Accepted ACCEPTED = Accepted.getInstance();

    public static void main(String[] args) throws Exception {
        String outputDir = args[0];
        String mode = args[1];
        String domain = args[2];
        String path = args[3];
        String operation = args[4];
        int messages = Integer.parseInt(args[5]);
        int bytes = Integer.parseInt(args[6]);
        int credit = Integer.parseInt(args[7]);

        if (!CLIENT.equalsIgnoreCase(mode)) {
            throw new RuntimeException("This impl currently supports client mode only");
        }

        final boolean sender;
        if (SEND.equalsIgnoreCase(operation)) {
          sender = true;
        } else if (RECEIVE.equalsIgnoreCase(operation)) {
          sender = false;
        } else {
          throw new java.lang.IllegalStateException("Unknown operation: " + mode);
        }

        CountDownLatch completionLatch = new CountDownLatch(1);
        URI uri = new URI("amqp://" + domain);

        String hostname = uri.getHost();
        int port = uri.getPort();
        if(port == -1) {
          port = DEFAULT_AMQP_PORT;
        }

        Vertx vertx = Vertx.vertx();

        ProtonClient client = ProtonClient.create(vertx);
        client.connect(hostname, port, res -> {
          if (res.succeeded()) {
            ProtonConnection connection = res.result();

            if (sender) {
              send(connection, path, messages, bytes, completionLatch);
            } else {
              receive(connection, path, messages, credit, completionLatch);
            }
          } else {
            res.cause().printStackTrace();
            completionLatch.countDown();
          }
        });

        // Await the operations completing, then shut down the Vertx instance.
        completionLatch.await();

        vertx.close();
    }

    private static void send(ProtonConnection connection, String address, int messages, int bytes, CountDownLatch latch) {
      connection.open();

      byte[] payloadContent = new byte[bytes];
      Arrays.fill(payloadContent, (byte) 120);

      AtomicLong count = new AtomicLong(1);

      ProtonSender sender = connection.createSender(address);
      sender.sendQueueDrainHandler(s -> {
        while (!sender.sendQueueFull() && count.get() <= messages) {
          Message msg = Message.Factory.create();

          msg.setMessageId(UnsignedLong.valueOf(count.get()));

          msg.setBody(new Data(new Binary(payloadContent)));

          Map<String, Object> props = new HashMap<>();
          msg.setApplicationProperties(new ApplicationProperties(props));
          long stime = System.currentTimeMillis();
          props.put("SendTime", stime);

          sender.send(msg);
          if(count.getAndIncrement() >= messages) {
            connection.closeHandler(x -> {
              latch.countDown();
            });
            connection.close();
          };
        }
      });
      sender.open();
    }

    private static void receive(ProtonConnection connection, String address, int messages, int credits, CountDownLatch latch) {
      connection.open();

      //TODO: adjust? The writer is [needlessly] synchronizing every write, the buffer may flush more/less often than desired?.
      PrintWriter out = new PrintWriter(new BufferedWriter(new OutputStreamWriter(System.out)));

      AtomicInteger count = new AtomicInteger(1);

      ProtonReceiver receiver = connection.createReceiver(address);
      receiver.setAutoAccept(false).setPrefetch(0).flow(credits);

      receiver.handler((delivery, msg) -> {
        Object id = msg.getMessageId();
        long stime = (Long) msg.getApplicationProperties().getValue().get("SendTime");
        long rtime = System.currentTimeMillis();

        out.printf("%s,%d,%d\n", id, stime, rtime);

        delivery.disposition(ACCEPTED, true);
        receiver.flow(1);

        if(count.getAndIncrement() >= messages) {
          out.flush();

          connection.closeHandler(x -> {
            latch.countDown();
          });
          connection.close();
        }
      }).open();
    }
}
