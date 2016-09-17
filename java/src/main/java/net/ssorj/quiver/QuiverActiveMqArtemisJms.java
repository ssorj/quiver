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

import java.lang.*;
import java.util.*;
import javax.jms.*;
import javax.naming.*;

public class QuiverActiveMqArtemisJms {
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
                "org.apache.activemq.artemis.jndi.ActiveMQInitialContextFactory");
        env.put("connectionFactory.ConnectionFactory", "tcp://" + domain);
        env.put("queue.queueLookup", path);

        try {
            context = new InitialContext(env);
            factory = (ConnectionFactory) context.lookup("ConnectionFactory");
            queue = (Destination) context.lookup("queueLookup");
        } catch (NamingException e) {
            throw new RuntimeException(e);
        }

        JmsClient client = new JmsClient(outputDir, factory, queue, operation,
                                         messages, bytes);
        
        try {
            client.run();
        } catch (RuntimeException e) {
            e.printStackTrace();
            throw e;
        }
    }
}
