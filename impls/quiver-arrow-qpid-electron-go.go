/*
Licensed to the Apache Software Foundation (ASF) under one
or more contributor license agreements.  See the NOTICE file
distributed with this work for additional information
regarding copyright ownership.  The ASF licenses this file
to you under the Apache License, Version 2.0 (the
"License"); you may not use this file except in compliance
with the License.  You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
KIND, either express or implied.  See the License for the
specific language governing permissions and limitations
under the License.
*/

package main

import (
	"fmt"
	"net"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"qpid.apache.org/amqp"
	"qpid.apache.org/electron"
)

func fail(format string, arg ...interface{}) {
	fmt.Fprintf(os.Stderr, "%s (%s): %s\n",
		filepath.Base(os.Args[0]), os.Args[3], fmt.Sprintf(format, arg...))
	os.Exit(1)
}

func failIfErr(err error) {
	if err != nil {
		fail("%v", err)
	}
}

type Arrow struct {
	connectionMode, channelMode, operation  string
	id, netAddr, path                       string
	messages                                int
	bodySize, creditWindow, transactionSize int
	flags                                   map[string]bool
	connectionOptions                       []electron.ConnectionOption

	container  electron.Container
	connection electron.Connection
	incoming   bool // True if we accepted some incoming endpoint
}

// Handle delivery outcomes on the sender.
// Close connection on error or completion.
func (a *Arrow) outcomes(out chan electron.Outcome) {
	for i := 0; i < a.messages; i++ {
		select {
		case o := <-out:
			if o.Status != electron.Accepted {
				fail("Unexpected delivery outcome: %v", o)
			}
		case <-a.connection.Done():
			fail("Not enough outcomes %v < %v", i, a.messages)
		}
	}
	a.connection.Close(nil)
}

// Compute the current time in milliseconds since the Epoch for quiver.
func now() int64 { t := time.Now(); return t.UnixNano() / int64(time.Millisecond) }

// Act as a sender
func (a *Arrow) sender(s electron.Sender) {
	out := make(chan electron.Outcome, a.creditWindow)
	go a.outcomes(out)
	m := amqp.NewMessageWith(strings.Repeat("x", int(a.bodySize)))
	m.SetApplicationProperties(make(map[string]interface{}, 1))
	for i := 0; i < a.messages; i++ {
		failIfErr(s.Error())
		id := i + 1
		m.SetMessageId(strconv.Itoa(id))
		t := now()
		m.ApplicationProperties()["SendTime"] = t
		fmt.Printf("%v,%v\n", id, t)
		s.SendAsync(m, out, nil) // May block for credit. Errors reported via outcomes
	}
	<-a.connection.Done() // Wait for outcomes() to close the connection
}

// Act as a receiver
func (a *Arrow) receiver(r electron.Receiver) {
	for i := 0; i < a.messages; i++ {
		rm, err := r.Receive()
		failIfErr(err)
		rm.Accept()
		m := rm.Message
		t := m.ApplicationProperties()["SendTime"]
		if t == nil {
			fail("no SendTime property in %v", m)
		}
		fmt.Printf("%v,%v,%v\n", m.MessageId(), t, now())
	}
	a.connection.Close(nil)
}

// Passively accept incoming endpoints.
func (a *Arrow) passive() {
	for in := range a.connection.Incoming() {
		a.incoming = true
		switch in := in.(type) {

		case *electron.IncomingSender:
			go a.sender(in.Accept().(electron.Sender))

		case *electron.IncomingReceiver:
			in.SetPrefetch(true)
			in.SetCapacity(a.creditWindow)
			go a.receiver(in.Accept().(electron.Receiver))

		default:
			in.Accept() // Accept connection and sessions unconditionally
		}
	}
}

// Actively initiate outgoing endpoints
func (a *Arrow) active() {
	switch a.operation {
	case "send":
		s, err := a.connection.Sender(electron.Target(a.path), electron.AtLeastOnce())
		failIfErr(err)
		a.sender(s)
	case "receive":
		var r electron.Receiver
		r, err := a.connection.Receiver(electron.Source(a.path), electron.Prefetch(true), electron.Capacity(a.creditWindow))
		failIfErr(err)
		a.receiver(r)
	default:
		fail("Bad operation: %v", a.operation)
	}
}

func (a *Arrow) connected() {
	switch a.channelMode {
	case "active":
		a.active()
	case "passive":
		a.passive()
	default:
		fail("Bad channel mode %v", a.channelMode)
	}
}

func (a *Arrow) run() {
	a.container = electron.NewContainer(a.id)
	switch a.connectionMode {
	case "client":
		c, err := a.container.Dial("tcp", a.netAddr, a.connectionOptions...)
		failIfErr(err)
		a.connection = c
		a.connected()
	case "server":
		l, err := net.Listen("tcp", a.netAddr)
		failIfErr(err)
		defer l.Close()
		for !a.incoming { // Ignore connections with no incoming activity
			a.connection, err = a.container.Accept(l, a.connectionOptions...)
			failIfErr(err)
			a.connected()
		}

	default:
		fail("bad connection mode %v", a.connectionMode)
	}
}

func intArg(i int) int {
	n, err := strconv.Atoi(os.Args[i])
	if err != nil {
		fail("arg[%v] not integer: %v", i, err)
	}
	return n
}
func flagArg(i int) map[string]bool {
	s := strings.TrimSpace(os.Args[i])
	var flags map[string]bool
	if len(s) > 0 {
		flags := make(map[string]bool)
		for _, key := range strings.Split(s, ",") {
			flags[key] = true
		}
	}
	return flags
}

func main() {
	if len(os.Args) == 1 {
		fmt.Printf("Qpid Electron Go")
		os.Exit(0)
	}
	want := 13
	if len(os.Args) != want {
		fail("incorrect number of arguments: want %v, got %v", want, len(os.Args))
	}
	a := Arrow{
		connectionMode:  os.Args[1],
		channelMode:     os.Args[2],
		operation:       os.Args[3],
		id:              os.Args[4],
		netAddr:         fmt.Sprintf("%v:%v", os.Args[5], os.Args[6]),
		path:            os.Args[7],
		messages:        intArg(8),
		bodySize:        intArg(9),
		creditWindow:    intArg(10),
		transactionSize: intArg(11),
		flags:           flagArg(12),

		connectionOptions: []electron.ConnectionOption{electron.SASLAllowedMechs("ANONYMOUS")},
	}

	if a.transactionSize > 0 {
		fail("transactions not supported")
	}
	a.run()
}
