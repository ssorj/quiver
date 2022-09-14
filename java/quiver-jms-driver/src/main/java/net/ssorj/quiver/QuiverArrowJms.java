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

import java.io.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;
import javax.naming.*;
import jakarta.jms.*;

public class QuiverArrowJms {
    public static void main(final String[] args) {
        try {
            doMain(args);
        } catch (Exception e) {
            e.printStackTrace();
            System.exit(1);
        }
    }

    public static void doMain(final String[] args) throws Exception {
        final HashMap<String, String> kwargs = new HashMap<>();

        for (String arg : args) {
            final String[] elems = arg.split("=", 2);
            kwargs.put(elems[0], elems[1]);
        }

        final String connectionMode = kwargs.get("connection-mode");
        final String channelMode = kwargs.get("channel-mode");
        final String operation = kwargs.get("operation");
        final String path = kwargs.get("path");
        final int desiredDuration = Integer.parseInt(kwargs.get("duration"));
        final int desiredCount = Integer.parseInt(kwargs.get("count"));
        final int desiredRate = Integer.parseInt(kwargs.get("rate"));
        final int bodySize = Integer.parseInt(kwargs.get("body-size"));
        final int transactionSize = Integer.parseInt(kwargs.get("transaction-size"));
        final boolean durable = Integer.parseInt(kwargs.get("durable")) == 1;
        final boolean setMessageID = Integer.parseInt(kwargs.get("set-message-id")) == 1;

        if (!connectionMode.equals("client")) {
            throw new RuntimeException("This impl supports client mode only");
        }

        if (!channelMode.equals("active")) {
            throw new RuntimeException("This impl supports active mode only");
        }

        final String url = System.getProperty("arrow.jms.url");
        assert url != null;

        final Hashtable<Object, Object> env = new Hashtable<Object, Object>();
        env.put("connectionFactory.ConnectionFactory", url);
        env.put("brokerURL", url);
        env.put("queue.queueLookup", path);

        final Context context = new InitialContext(env);
        final ConnectionFactory factory = (ConnectionFactory) context.lookup("ConnectionFactory");
        final Destination queue = (Destination) context.lookup("queueLookup");

        final Client client = new Client(factory, queue, operation, desiredDuration, desiredCount, desiredRate,
                                         bodySize, transactionSize, durable, setMessageID);

        client.run();
    }
}

class Client {
    protected final ConnectionFactory factory;
    protected final Destination queue;
    protected final String operation;
    protected final int desiredDuration;
    protected final int desiredCount;
    protected final int desiredRate;
    protected final int bodySize;
    protected final int transactionSize;

    protected final boolean durable;
    protected final boolean setMessageID;

    protected int sent;
    protected int received;

    protected final AtomicBoolean stopping = new AtomicBoolean();
    private final long nanoPeriod;

    Client(final ConnectionFactory factory, final Destination queue, final String operation,
           final int desiredDuration, final int desiredCount, final int desiredRate,
           final int bodySize, final int transactionSize, final boolean durable, final boolean setMessageID) {
        this.factory = factory;
        this.queue = queue;
        this.operation = operation;
        this.desiredDuration = desiredDuration;
        this.desiredCount = desiredCount;
        this.desiredRate = desiredRate;
        this.bodySize = bodySize;
        this.transactionSize = transactionSize;
        this.durable = durable;
        this.setMessageID = setMessageID;

        if (this.desiredRate > 0) {
            this.nanoPeriod = TimeUnit.SECONDS.toNanos(1) / this.desiredRate;
        } else {
            this.nanoPeriod = 0;
        }

        this.sent = 0;
        this.received = 0;
    }

    void run() {
        try {
            final Connection conn = factory.createConnection();

            conn.start();

            if (desiredDuration > 0) {
                final Timer timer = new Timer(true);
                final TimerTask task = new TimerTask() {
                        public void run() {
                            stopping.lazySet(true);
                        }
                    };

                timer.schedule(task, desiredDuration * 1000);
            }

            final Session session;

            if (transactionSize > 0) {
                session = conn.createSession(true, Session.SESSION_TRANSACTED);
            } else {
                session = conn.createSession(false, Session.AUTO_ACKNOWLEDGE);
            }

            try {
                if (operation.equals("send")) {
                    sendMessages(session);
                } else if (operation.equals("receive")) {
                    receiveMessages(session);
                } else {
                    throw new java.lang.IllegalStateException();
                }
            } catch (JMSException e) {
                // Ignore error from remote close
                return;
            }

            if (transactionSize > 0) {
                session.commit();
            }

            conn.close();
        } catch (IOException e) {
            throw new RuntimeException(e);
        } catch (JMSException e) {
            throw new RuntimeException(e);
        }
    }

    private static BufferedWriter getWriter() {
        return new BufferedWriter(new OutputStreamWriter(System.out));
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

    void sendMessages(final Session session) throws IOException, JMSException {
        final StringBuilder line = new StringBuilder();
        final BufferedWriter out = getWriter();
        final MessageProducer producer = session.createProducer(queue);
        final byte[] body = new byte[bodySize];
        final long nanoPeriod = this.nanoPeriod;
        final long startTime = System.nanoTime();
        long nextTime = startTime + nanoPeriod;

        Arrays.fill(body, (byte) 120);

        if (durable) {
            producer.setDeliveryMode(DeliveryMode.PERSISTENT);
        } else {
            producer.setDeliveryMode(DeliveryMode.NON_PERSISTENT);
        }

        producer.setDisableMessageTimestamp(true);

        if (this.setMessageID) {
            producer.setDisableMessageID(false);
        } else {
            producer.setDisableMessageID(true);
        }

        while (!stopping.get()) {
            final BytesMessage message = session.createBytesMessage();

            message.writeBytes(body);

            if (nanoPeriod > 0) {
                nextTime = waitUntilNextTime(nextTime, nanoPeriod);
            }

            final long stime = System.currentTimeMillis();
            message.setLongProperty("SendTime", stime);

            producer.send(message);

            sent += 1;

            line.setLength(0);
            out.append(line.append(stime).append(",0\n"));

            if (transactionSize > 0 && (sent % transactionSize) == 0) {
                session.commit();
            }

            if (sent == desiredCount) {
                break;
            }
        }

        out.flush();
    }

    void receiveMessages(Session session) throws IOException, JMSException {
        final StringBuilder line = new StringBuilder();
        final BufferedWriter out = getWriter();
        final MessageConsumer consumer = session.createConsumer(queue);

        while (!stopping.get()) {
            final Message message = consumer.receive(100);

            if (message == null) {
                continue;
            }

            received += 1;

            if (this.setMessageID) {
                final String id = message.getJMSMessageID();
            }

            final long stime = message.getLongProperty("SendTime");
            final long rtime = System.currentTimeMillis();

            line.setLength(0);
            out.append(line.append(stime).append(',').append(rtime).append('\n'));

            if (transactionSize > 0 && (received % transactionSize) == 0) {
                session.commit();
            }

            if (received == desiredCount) {
                break;
            }
        }

        out.flush();
    }
}
