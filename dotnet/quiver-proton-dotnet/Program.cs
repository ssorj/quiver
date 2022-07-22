/*
 * Licensed to the Apache Software Foundation (ASF) under one or more
 * contributor license agreements.  See the NOTICE file distributed with
 * this work for additional information regarding copyright ownership.
 * The ASF licenses this file to You under the Apache License, Version 2.0
 * (the "License"); you may not use this file except in compliance with
 * the License.  You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

using System;
using System.IO;
using System.Collections.Generic;
using System.Threading;
using System.Text;
using Apache.Qpid.Proton.Client;
using Apache.Qpid.Proton.Client.Exceptions;

namespace Quiver.Driver
{
   enum Operation
   {
      SEND,
      RECEIVE
   }

   class Program
   {
      private const string CLIENT = "client";
      private const string ACTIVE = "active";
      private const string AMQPS = "amqps";

      static void Main(string[] args)
      {
         // Buffer console output for lifetime of this application
         using StreamWriter bufferOutput = new(Console.OpenStandardOutput(8192));
         Console.SetOut(bufferOutput);

         try
         {
            MainOperation(args);
         }
         catch (Exception e)
         {
            Console.WriteLine("Error caught: " + e.Message);
            Console.WriteLine(e);

            bufferOutput.Flush();
            Environment.Exit(1);
         }
         finally
         {
            bufferOutput.Flush();
         }
      }

      private static void MainOperation(string[] args)
      {
         Dictionary<string, string> kwargs = new();

         foreach (string arg in args)
         {
            string[] elems = arg.Split("=", 2);
            kwargs[elems[0]] = elems[1];
            // Console.Error.WriteLine("Arg key=" + elems[0] + " value=" + elems[1]);
         }

         string connectionMode = kwargs.GetValueOrDefault("connection-mode", "").ToLower();
         string channelMode = kwargs.GetValueOrDefault("channel-mode", "").ToLower();
         Operation operation = (Operation)Enum.Parse(typeof(Operation), kwargs.GetValueOrDefault("operation", "SEND").ToUpper());
         string id = kwargs.GetValueOrDefault("id", "");
         string scheme = kwargs.GetValueOrDefault("scheme", "");
         string host = kwargs.GetValueOrDefault("host", "");
         int port = int.Parse(kwargs.GetValueOrDefault("port", "5672"));
         string address = kwargs.GetValueOrDefault("path", "");
         string username = kwargs.GetValueOrDefault("username", "");
         string password = kwargs.GetValueOrDefault("password", "");
         string cert = kwargs.GetValueOrDefault("cert", "");
         string key = kwargs.GetValueOrDefault("key", "");
         int desiredDuration = int.Parse(kwargs.GetValueOrDefault("duration", "0"));
         int desiredCount = int.Parse(kwargs.GetValueOrDefault("count", "0"));
         int bodySize = int.Parse(kwargs.GetValueOrDefault("body-size", "0"));
         uint creditWindow = uint.Parse(kwargs.GetValueOrDefault("credit-window", "10"));
         int transactionSize = int.Parse(kwargs.GetValueOrDefault("transaction-size", "0"));
         bool durable = Convert.ToBoolean(int.Parse(kwargs.GetValueOrDefault("durable", "0")));
         bool setMessageID = Convert.ToBoolean(int.Parse(kwargs.GetValueOrDefault("set-message-id", "0")));

         if (!CLIENT.Equals(connectionMode))
         {
            throw new NotSupportedException("This impl currently supports client mode only");
         }

         if (!ACTIVE.Equals(channelMode))
         {
            throw new NotSupportedException("This impl currently supports active mode only");
         }

         if (transactionSize > 0)
         {
            throw new NotSupportedException("This impl doesn't support transactions");
         }

         IClient client = IClient.Create(new ClientOptions()
         {
            Id = id
         });

         ConnectionOptions options = new()
         {
            User = string.IsNullOrEmpty(username) ? null : username,
            Password = string.IsNullOrEmpty(password) ? null : password,
            SslEnabled = AMQPS.Equals(scheme)
         };

         if (options.SslEnabled)
         {
            options.SslOptions.VerifyHost = false;
            options.SslOptions.RemoteValidationCallbackOverride = (sender, certificates, chain, errors) =>
            {
               return true;
            };

            // TODO Certificate chain enablement if keystore provided.
         }

         Arrow arrow = new(client, options, host, port, address, operation,
                           creditWindow, desiredDuration, desiredCount,
                           bodySize, transactionSize, durable, setMessageID);

         arrow.Run();
      }

      private sealed class Arrow
      {
         private readonly IClient client;
         private readonly ConnectionOptions options;
         private readonly Operation operation;
         private readonly string host;
         private readonly int port;
         private readonly string address;
         private readonly int desiredDuration;
         private readonly int desiredCount;
         private readonly uint prefetch;
         private readonly int bodySize;
         private readonly int transactionSize;
         private readonly bool durable;
         private readonly bool setMessageID;

         private readonly DateTime timeBase = new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc);

         // Tracks actual state of the arrow as it runs
         private uint sent;
         private uint received;
         private volatile bool stopping = false;

         public Arrow(IClient client, ConnectionOptions options, string host, int port, string address,
                      Operation operation, uint prefetch, int desiredDuration, int desiredCount, int bodySize,
                      int transactionSize, bool durable, bool setMessageID)
         {
            this.client = client;
            this.options = options;
            this.host = host;
            this.port = port;
            this.address = address;
            this.operation = operation;
            this.prefetch = prefetch;
            this.desiredDuration = desiredDuration;
            this.desiredCount = desiredCount;
            this.bodySize = bodySize;
            this.transactionSize = transactionSize;
            this.durable = durable;
            this.setMessageID = setMessageID;
         }

         public void Run()
         {
            using IConnection connection = client.Connect(host, port, options);

            Timer? timer = null;

            if (desiredDuration > 0)
            {
               timer = new((state) => stopping = true, this, desiredDuration * 1000, Timeout.Infinite);
            };

            try
            {
               switch (operation)
               {
                  case Operation.RECEIVE:
                     ReceiveMessages(connection);
                     break;
                  case Operation.SEND:
                     SendMessages(connection);
                     break;
               }
            }
            catch (Exception ex)
            {
               Console.Error.WriteLine(ex.Message);
               if (ex is ClientException || ex is IOException)
               {
                  // Ignore error from remote close
                  return;
               }
            }
            finally
            {
               timer?.Dispose();
            }
         }

         void SendMessages(IConnection connection)
         {
            StringBuilder line = new();
            SenderOptions senderOptions = new();
            senderOptions.TargetOptions.Capabilities = new string[] { "queue" };

            using ISender sender = connection.OpenSender(address, senderOptions);
            byte[] body = new byte[bodySize];

            Array.Fill(body, (byte)120);

            ITracker? lastSentTracker = null;

            if (transactionSize > 0)
            {
               sender.Session.BeginTransaction();
            }

            while (!stopping)
            {
               IMessage<byte[]> message = IMessage<byte[]>.Create(body);

               if (durable)
               {
                  message.Durable = true;
               }

               if (setMessageID)
               {
                  message.MessageId = sent.ToString();
               }

               long sentAt = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
               message.SetProperty("SendTime", sentAt);

               lastSentTracker = sender.Send(message);
               sent += 1;

               line.Clear();
               Console.Write(line.Append(sentAt).Append(",0\n"));

               if (transactionSize > 0 && (sent % transactionSize) == 0)
               {
                  sender.Session.CommitTransaction();
                  sender.Session.BeginTransaction();
               }

               if (sent == desiredCount)
               {
                  break;
               }
            }

            try
            {
               lastSentTracker?.AwaitSettlement();
            }
            catch (ClientException e)
            {
               Console.Error.WriteLine(e.Message);
               throw new IOException("Error While waiting on final remote disposition", e);
            }

            if (transactionSize > 0)
            {
               sender.Session.CommitTransaction();
            }
         }

         void ReceiveMessages(IConnection connection)
         {
            StringBuilder line = new();
            ReceiverOptions receiverOptions = new();
            receiverOptions.SourceOptions.Capabilities = new string[] { "queue" };
            receiverOptions.CreditWindow = prefetch;

            using IReceiver receiver = connection.OpenReceiver(address, receiverOptions);

            if (transactionSize > 0)
            {
               receiver.Session.BeginTransaction();
            }

            while (!stopping)
            {
               IDelivery delivery = receiver.Receive(TimeSpan.FromMilliseconds(100));

               if (delivery == null)
               {
                  continue;
               }

               IMessage<object> message = delivery.Message();

               received += 1;

               if (setMessageID)
               {
                  _ = message.MessageId;
               }

               long sentAt = (long)message.GetProperty("SendTime");
               long receivedAt = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();

               line.Clear();
               Console.Write(line.Append(sentAt).Append(',').Append(receivedAt).Append('\n'));

               if (transactionSize > 0 && (received % transactionSize) == 0)
               {
                  receiver.Session.CommitTransaction();
                  receiver.Session.BeginTransaction();
               }

               if (received == desiredCount)
               {
                  break;
               }
            }

            if (transactionSize > 0)
            {
               receiver.Session.CommitTransaction();
            }
         }
      }
   }
}
