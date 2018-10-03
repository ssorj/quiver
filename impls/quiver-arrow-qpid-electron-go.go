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
	fmt.Fprintf(os.Stderr, "%s: %s\n", filepath.Base(os.Args[0]), fmt.Sprintf(format, arg...))
	fmt.Fprintln(os.Stderr, os.Args[1:])
	os.Exit(1)
}

func failIfErr(err error) {
	if err != nil {
		fail("%v", err)
	}
}

type Arrow struct {
	connectionMode, channelMode string
	operation                   string
	id, netAddr, path           string
	count                       int
	bodySize, creditWindow      int
	durable                     bool

	container  electron.Container
	connection electron.Connection
	done       bool
}

// Handle delivery outcomes on the sender.
// Close connection on error or completion.
func (a *Arrow) outcomes(out chan electron.Outcome) {
	for i := 0; i < a.count; i++ {
		select {
		case o := <-out:
			if o.Status != electron.Accepted {
				fail("Unexpected delivery outcome: %v", o)
			}
		case <-a.connection.Done():
			fail("Not enough outcomes %v < %v", i, a.count)
		}
	}
	a.connection.Close(nil)
}

// Convert Go time.Time into milliseconds since Unix Epoch.
func now() int64 { return time.Now().UnixNano() / int64(time.Millisecond) }

// Act as a sender
func (a *Arrow) sender(s electron.Sender) {
	out := make(chan electron.Outcome, a.creditWindow)
	go a.outcomes(out)
	body := strings.Repeat("x", int(a.bodySize))
	props := make(map[string]interface{})
	for i := 0; i < a.count; i++ {
		failIfErr(s.Error())
		msg := amqp.NewMessageWith(body)
		id := i + 1
		msg.SetMessageId(strconv.Itoa(id))
		msg.SetDurable(a.durable)
		t := now()
		props["SendTime"] = t // time.Time encodes as AMQP timestamp
		msg.SetApplicationProperties(props)
		fmt.Printf("%v,%v\n", id, t)
		s.SendAsync(msg, out, nil) // May block for credit. Errors reported via outcomes
	}
	a.done = true
	<-a.connection.Done() // Wait for outcomes() to close the connection
}

// Act as a receiver
func (a *Arrow) receiver(r electron.Receiver) {
	for i := 0; i < a.count; i++ {
		rm, err := r.Receive()
		failIfErr(err)
		rm.Accept()
		m := rm.Message
		if t, ok := m.ApplicationProperties()["SendTime"]; ok {
			fmt.Printf("%v,%v,%v\n", m.MessageId(), t, now())
		} else {
			fail("No SendTime property in %v", m)
		}
	}
	a.done = true
	a.connection.Close(nil)
}

// Passively accept incoming endpoints.
func (a *Arrow) passive() {
	for in := range a.connection.Incoming() {
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
		c, err := a.container.Dial("tcp", a.netAddr, electron.SASLAllowedMechs("ANONYMOUS"))
		failIfErr(err)
		a.connection = c
		a.connected()
	case "server":
		l, err := net.Listen("tcp", a.netAddr)
		failIfErr(err)
		defer l.Close()
		for !a.done { // May get dummy probe connections
			a.connection, err = a.container.Accept(l,
				electron.Server(), electron.SASLAllowedMechs("ANONYMOUS"))
			failIfErr(err)
			a.connected()
		}

	default:
		fail("bad connection mode %v", a.connectionMode)
	}
}

type kwargs map[string]string

func parseArgs() kwargs {
	kw := make(map[string]string)
	for _, arg := range os.Args[1:] {
		kv := strings.SplitN(arg, "=", 2)
		kw[kv[0]] = kv[1]
	}
	return kw
}

func (kw kwargs) Int(k string) int {
	n, err := strconv.Atoi(kw[k])
	if err != nil {
		fail("\"%v=%v\" not integer: %v", k, kw[k], err)
	}
	return n
}

func (kw kwargs) Bool(k string) bool {
	b, err := strconv.ParseBool(kw[k])
	if err != nil {
		fail("\"%v=%v\" not boolean: %v", k, kw[k], err)
	}
	return b
}

func main() {
	if len(os.Args) == 1 {
		fmt.Printf("Qpid Electron Go")
		os.Exit(0)
	}

	kwargs := parseArgs()

	if n := kwargs.Int("transaction-size"); n > 0 {
		fail("Transactions not supported")
	}

	a := Arrow{
		connectionMode: kwargs["connection-mode"],
		channelMode:    kwargs["channel-mode"],
		operation:      kwargs["operation"],
		id:             kwargs["id"],
		netAddr:        fmt.Sprintf("%v:%v", kwargs["host"], kwargs["port"]),
		path:           kwargs["path"],
		count:          kwargs.Int("count"),
		bodySize:       kwargs.Int("body-size"),
		creditWindow:   kwargs.Int("credit-window"),
		durable:        kwargs.Bool("durable"),
	}
	a.run()
}
