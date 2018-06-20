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

import javax.jms.*;
import javax.naming.Context;
import javax.naming.InitialContext;
import java.io.PrintWriter;
import java.util.Arrays;
import java.util.Hashtable;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.locks.LockSupport;

public class QuiverArrowJms {
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
        String path = args[6];
        int messages = Integer.parseInt(args[7]);
        int bodySize = Integer.parseInt(args[8]);
        int transactionSize = Integer.parseInt(args[10]);
        String[] flags = args[11].split(",");
        int target = Integer.parseInt(args[12]);

        if (!connectionMode.equals("client")) {
            throw new RuntimeException("This impl supports client mode only");
        }

        if (!channelMode.equals("active")) {
            throw new RuntimeException("This impl supports active mode only");
        }

        String url = System.getProperty("arrow.jms.url");
        assert url != null;

        Hashtable<Object, Object> env = new Hashtable<Object, Object>();
        env.put("connectionFactory.ConnectionFactory", url);
        env.put("brokerURL", url);
        env.put("queue.queueLookup", path);

        Context context = new InitialContext(env);
        ConnectionFactory factory = (ConnectionFactory) context.lookup("ConnectionFactory");
        Destination queue = (Destination) context.lookup("queueLookup");

        Client client = new Client(factory, queue, operation, messages, bodySize, transactionSize, flags, target);

        client.run();
    }
}

class Client {
    protected final ConnectionFactory factory;
    protected final Destination queue;
    protected final String operation;
    protected final int messages;
    protected final int bodySize;
    protected final int transactionSize;

    protected final boolean durable;

    protected int sent;
    protected int received;
    private final long nanoPeriod;

    Client(ConnectionFactory factory, Destination queue, String operation,
           int messages, int bodySize, int transactionSize, String[] flags, int target) {
        this.factory = factory;
        this.queue = queue;
        this.operation = operation;
        this.messages = messages;
        this.bodySize = bodySize;
        this.transactionSize = transactionSize;
        this.durable = Arrays.asList(flags).contains("durable");
        this.nanoPeriod = target > 0 ? TimeUnit.SECONDS.toNanos(1) / target : 0;
        this.sent = 0;
        this.received = 0;
    }

    void run() {
        try {
            Connection conn = factory.createConnection();
            conn.start();

            final Session session;

            if (transactionSize > 0) {
                session = conn.createSession(true, Session.SESSION_TRANSACTED);
            } else {
                session = conn.createSession(false, Session.AUTO_ACKNOWLEDGE);
            }

            if (operation.equals("send")) {
                sendMessages(session);
            } else if (operation.equals("receive")) {
                receiveMessages(session);
            } else {
                throw new java.lang.IllegalStateException();
            }

            if (transactionSize > 0) {
                session.commit();
            }

            conn.close();
        } catch (JMSException e) {
            throw new RuntimeException(e);
        }
    }

    private static PrintWriter getOutputWriter() {
        return new PrintWriter(System.out);
    }

    private static long waitUntilNextTime(final long nextTime, final long nanoPeriod) {
        assert nanoPeriod > 0;
        long waitNanos;
        do {
            waitNanos = nextTime - System.nanoTime();
            if (waitNanos > 0) {
                LockSupport.parkNanos(waitNanos);
            }
        } while (waitNanos > 0);
        return nextTime + nanoPeriod;
    }

    void sendMessages(Session session) throws JMSException {
        PrintWriter out = getOutputWriter();
        MessageProducer producer = session.createProducer(queue);

        if (durable) {
            producer.setDeliveryMode(DeliveryMode.PERSISTENT);
        } else {
            producer.setDeliveryMode(DeliveryMode.NON_PERSISTENT);
        }

        producer.setDisableMessageTimestamp(true);

        byte[] body = new byte[bodySize];
        Arrays.fill(body, (byte) 120);
        final long nanoPeriod = this.nanoPeriod;
        final long start = System.nanoTime();
        long nextTime = start + nanoPeriod;

        while (sent < messages) {
            BytesMessage message = session.createBytesMessage();
            message.writeBytes(body);
            if (nanoPeriod > 0) {
                nextTime = waitUntilNextTime(nextTime, nanoPeriod);
            }
            final long stime = System.currentTimeMillis();
            message.setLongProperty("SendTime", stime);
            producer.send(message);

            out.printf("%s,%d\n", message.getJMSMessageID(), stime);

            sent += 1;

            if (transactionSize > 0 && (sent % transactionSize) == 0) {
                session.commit();
            }
        }

        out.flush();
    }

    void receiveMessages(Session session) throws JMSException {
        PrintWriter out = getOutputWriter();
        MessageConsumer consumer = session.createConsumer(queue);

        while (received < messages) {
            BytesMessage message = (BytesMessage) consumer.receive();

            if (message == null) {
                throw new RuntimeException("Null receive");
            }

            String id = message.getJMSMessageID();
            long stime = message.getLongProperty("SendTime");
            long rtime = System.currentTimeMillis();

            out.printf("%s,%d,%d\n", id, stime, rtime);

            received += 1;

            if (transactionSize > 0 && (received % transactionSize) == 0) {
                session.commit();
            }
        }

        out.flush();
    }
}
