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

import java.io.*;
import java.lang.*;
import java.util.*;
import javax.jms.*;
import javax.naming.*;

public class QuiverQpidJms {
    public static void main(String[] args) {
        String outputDir = args[0];
        String mode = args[1];
        String domain = args[2];
        String path = args[3];
        String operation = args[4];
        int messages = Integer.parseInt(args[5]);
        int bytes = Integer.parseInt(args[6]);
        int credit = Integer.parseInt(args[7]);

        if (!mode.equals("client")) {
            throw new RuntimeException("This impl supports client mode only");
        }
        
        Hashtable<Object, Object> env = new Hashtable<Object, Object>();
        Context context;
        ConnectionFactory factory;
        Destination queue;

        env.put(Context.INITIAL_CONTEXT_FACTORY,
                "org.apache.qpid.jms.jndi.JmsInitialContextFactory");
        env.put("connectionfactory.factoryLookup", "amqp://" + domain);
        env.put("queue.queueLookup", path);

        try {
            context = new InitialContext(env);
            factory = (ConnectionFactory) context.lookup("factoryLookup");
            queue = (Destination) context.lookup("queueLookup");
        } catch (NamingException e) {
            throw new RuntimeException(e);
        }

        Client client = new Client(outputDir, factory, queue, operation,
                                   messages, bytes);
        
        try {
            client.run();
        } catch (RuntimeException e) {
            e.printStackTrace();
            throw e;
        }
    }
}

class Client {
    protected final String outputDir;
    protected final ConnectionFactory factory;
    protected final Destination queue;
    protected final String operation;
    protected final int messages;
    protected final int bytes;
    protected int transfers;
    
    Client(String outputDir, ConnectionFactory factory, Destination queue,
           String operation, int messages, int bytes) {
        this.outputDir = outputDir;
        this.factory = factory;
        this.queue = queue;
        this.operation = operation;
        this.messages = messages;
        this.bytes = bytes;
        this.transfers = 0;
    }

    void run() {
        try {
            Connection conn = this.factory.createConnection();
            conn.start();

            Session session = conn.createSession(false, Session.AUTO_ACKNOWLEDGE);

            if (this.operation.equals("send")) {
                this.sendMessages(session);
            } else if (this.operation.equals("receive")) {
                this.receiveMessages(session);
            } else {
                throw new java.lang.IllegalStateException();
            }

            conn.close();
        } catch (JMSException e) {
            throw new RuntimeException(e);
        }
    }

    void sendMessages(Session session) throws JMSException {
        MessageProducer producer = session.createProducer(this.queue);
        producer.setDeliveryMode(DeliveryMode.NON_PERSISTENT);
        producer.setDisableMessageTimestamp(true);
        
        byte[] body = new byte[this.bytes];
        Arrays.fill(body, (byte) 120);
        
        while (this.transfers < this.messages) {
            BytesMessage message = session.createBytesMessage();
            double stime = (double) System.currentTimeMillis() / 1000.0;

            message.writeBytes(body);
            message.setDoubleProperty("SendTime", stime);
            
            producer.send(message);

            this.transfers += 1;
        }
    }

    void receiveMessages(Session session) throws JMSException {
        PrintWriter out = new PrintWriter(new BufferedWriter(new OutputStreamWriter(System.out)));
        MessageConsumer consumer = session.createConsumer(this.queue);

        while (this.transfers < this.messages) {
            BytesMessage message = (BytesMessage) consumer.receive();

            if (message == null) {
                throw new RuntimeException("Null response");
            }

            message.acknowledge();

            String id = message.getJMSMessageID();
            double stime = message.getDoubleProperty("SendTime");
            double rtime = (double) System.currentTimeMillis() / 1000.0;

            out.printf("%s,%.3f,%.3f\n", id, stime, rtime);
            
            this.transfers += 1;
        }

        out.flush();
    }
}
