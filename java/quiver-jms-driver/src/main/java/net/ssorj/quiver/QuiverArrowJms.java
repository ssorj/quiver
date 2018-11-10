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
import java.util.concurrent.atomic.*;
import javax.jms.*;
import javax.naming.*;

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
        final String connectionMode = args[0];
        final String channelMode = args[1];
        final String operation = args[2];
        final String path = args[6];
        final int desiredDuration = Integer.parseInt(args[7]);
        final int desiredCount = Integer.parseInt(args[8]);
        final int bodySize = Integer.parseInt(args[9]);
        final int transactionSize = Integer.parseInt(args[11]);
        final String[] flags = args[12].split(",");

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

        final Client client = new Client(factory, queue, operation, desiredDuration, desiredCount, bodySize,
                                         transactionSize, flags);

        client.run();
    }
}

class Client {
    protected final ConnectionFactory factory;
    protected final Destination queue;
    protected final String operation;
    protected final int desiredDuration;
    protected final int desiredCount;
    protected final int bodySize;
    protected final int transactionSize;

    protected final boolean durable;

    protected int sent;
    protected int received;
    protected final AtomicBoolean stopping = new AtomicBoolean();

    Client(final ConnectionFactory factory, final Destination queue, final String operation,
           final int desiredDuration, final int desiredCount, final int bodySize,
           final int transactionSize, final String[] flags) {
        this.factory = factory;
        this.queue = queue;
        this.operation = operation;
        this.desiredDuration = desiredDuration;
        this.desiredCount = desiredCount;
        this.bodySize = bodySize;
        this.transactionSize = transactionSize;

        this.durable = Arrays.asList(flags).contains("durable");
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

    void sendMessages(final Session session) throws IOException, JMSException {
        final StringBuilder line = new StringBuilder();
        final BufferedWriter out = getWriter();
        final MessageProducer producer = session.createProducer(queue);
        final byte[] body = new byte[bodySize];

        Arrays.fill(body, (byte) 120);

        if (durable) {
            producer.setDeliveryMode(DeliveryMode.PERSISTENT);
        } else {
            producer.setDeliveryMode(DeliveryMode.NON_PERSISTENT);
        }

        producer.setDisableMessageTimestamp(true);

        while (!stopping.get()) {
            final BytesMessage message = session.createBytesMessage();
            final long stime = System.currentTimeMillis();

            message.writeBytes(body);
            message.setLongProperty("SendTime", stime);

            producer.send(message);
            sent += 1;

            line.setLength(0);
            out.append(line.append(message.getJMSMessageID()).append(',').append(stime).append('\n'));

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

            final String id = message.getJMSMessageID();
            final long stime = message.getLongProperty("SendTime");
            final long rtime = System.currentTimeMillis();

            line.setLength(0);
            out.append(line.append(id).append(',').append(stime).append(',').append(rtime).append('\n'));

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
