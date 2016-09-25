# Quiver

Tools for testing the performance of messaging clients and servers.

    [Start an AMQP server]
    $ (quiver-arrow q0 receive &); quiver-arrow q0 send
    *        6,115         6,022 messages/s         112.0 ms avg latency
    *       12,976         6,650 messages/s         303.3 ms avg latency
    [...]
    *      992,299         6,681 messages/s      24,297.5 ms avg latency
    *      999,204         6,802 messages/s      24,435.7 ms avg latency
    --------------------------------------------------------------------------------
    Duration:                                               162.9 s
    Message count:                                      1,000,000 messages
    Message rate:                                           6,140 messages/s
    Latency average:                                     13,998.2 ms
    Latency by quartile:         6,844 | 14,337 | 20,966 | 25,335 ms
    --------------------------------------------------------------------------------

## Overview

Quiver implementations are native clients (and sometimes also servers)
in various languages and APIs that send or receive messages and dump
raw information about the transfers to standard output.  They are
deliberately simple.

`quiver-arrow` runs an implementation in send or receive mode and
captures its output.  It has options for defining the execution
parameters, selecting the implementation, and reporting statistics.

`quiver` makes it easy to launch many `quiver-arrow` instances.
In the future, it will collate the results from the individual
`quiver-arrow` runs and produce a consolidated report.

## Installation

### Installing from source

By default, installs from source go to `$HOME/.local`.  Make sure
`$HOME/.local/bin` is in your path.

    $ cd quiver
    $ make install

### Using packages

    $ sudo dnf enable jross/ssorj
    $ sudo dnf install quiver

If you don't have `dnf`, use the repo files at
<https://copr.fedorainfracloud.org/coprs/jross/ssorj/>.

## Development

To setup paths in your development environment, source the `devel.sh`
script from the project directory.

    $ cd quiver/
    $ source devel.sh

The `devel` make target creates a local installation in your checkout.

    $ make devel

## Project layout

    devel.sh              # Sets up your project environment
    Makefile              # Defines the make targets
    bin/                  # Command-line tools
    exec/                 # Quiver implementations
    python/               # Python library code
    scripts/              # Scripts called by Makefile rules
    java/                 # Java library code
    javascript/           # JavaScript library code
    build/                # The default build location
    install/              # The devel install location

## Make targets

In the development environment, most things are accomplished by
running make targets.  These are the important ones:

    $ make build         # Builds the code
    $ make install       # Installs the code
    $ make clean         # Removes build/ and install/
    $ make devel         # Cleans, builds, installs, tests sanity
    $ make test          # Runs the test suite

## Command-line interface

### `quiver-arrow`

This command sends or receives AMQP messages as fast as it can.  When
the requested transfers are done, it reports the throughput and
latency of the overall set, from the first send to the last receive.

    usage: quiver-arrow [-h] [-n COUNT] [--impl NAME] [--bytes COUNT] [--credit COUNT]
                        [--timeout SECONDS] [--server] [--output DIRECTORY] [--quiet] [--debug]
                        ADDRESS OPERATION

    Test the performance of messaging clients and servers

    positional arguments:
      ADDRESS               The location of a message queue
      OPERATION             Either 'send' or 'receive'

    optional arguments:
      -h, --help            show this help message and exit
      -n COUNT, --messages COUNT
                            Send or receive COUNT messages (default: 1000000)
      --impl NAME           Use NAME implementation (default: qpid-proton-python)
      --bytes COUNT         Send message bodies containing COUNT bytes (default: 100)
      --credit COUNT        Sustain credit for COUNT incoming transfers (default: 1000)
      --timeout SECONDS     Fail after SECONDS without transfers (default: 10)
      --server              Operate in server mode (default: False)
      --output DIRECTORY    Save output files to DIRECTORY (default: None)
      --quiet               Print nothing to the console (default: False)
      --debug               Print debug messages (default: False)

    operations:
      send                  Send messages
      receive               Receive messages

    addresses:
      [//DOMAIN/]PATH                 The default domain is 'localhost'
      //example.net/jobs
      //10.0.0.10:5672/jobs/alpha
      //localhost/q0
      q0

    implementations:
      activemq-artemis-jms            Client mode only; requires Artemis server
      activemq-jms                    Client mode only; ActiveMQ or Artemis server
      qpid-jms [jms]                  Client mode only
      qpid-messaging-cpp              Client mode only
      qpid-messaging-python           Client mode only
      qpid-proton-python [python]
      rhea [javascript]               Client mode only at the moment
      vertx-proton                    Client mode only

### `quiver`

This command starts sender-receiver pairs.  Each sender or receiver is
an invocation of the `quiver-arrow` command.  Arguments not processed
by `quiver` are passed to `quiver-arrow`.

    usage: quiver [-h] [--pairs COUNT] [--senders COUNT]
                  [--receivers COUNT] ADDRESS

    Launch Quiver senders and receivers

    Arguments not processed by 'quiver' are passed to the 'quiver-arrow'
    command.  See the output of 'quiver-arrow --help'.

    positional arguments:
      ADDRESS            The location of a message queue

    optional arguments:
      -h, --help         show this help message and exit
      --pairs COUNT      Launch COUNT sender-receiver pairs (default: 1)
      --senders COUNT    Launch COUNT senders (default: 1)
      --receivers COUNT  Launch COUNT receivers (default: 1)

## Examples

### Running Quiver with Dispatch Router

    $ qdrouterd &
    $ quiver q0

### Running Quiver with Artemis

    $ <instance-dir>/bin/artemis run &
    $ <instance-dir>/bin/artemis destination create --name q0 --type core-queue
    $ quiver q0
    
### Running Quiver with the Qpid C++ broker

    $ qpidd --auth no &
    $ qpid-config add queue q0
    $ quiver q0

### Running Quiver peer-to-peer

    $ quiver-arrow --server q0 receive &
    $ quiver-arrow q0 send

    [or]

    $ quiver-arrow --server q0 send &
    $ quiver-arrow q0 receive

## Implementations

The `quiver-arrow` command is a wrapper that invokes an implementation
executable using standard arguments.  `quiver-arrow` tries to take
responsibility for "cooking" its inputs so implementations can focus
on mechanics.  By the same token, implementation outputs are
intentionally left raw so `quiver-arrow` can do the work of presenting
the results.

### Input

Implementations must process the following positional arguments.

    [1] output-dir      A directory for output files
    [2] mode            'client' or 'server'
    [3] domain          <host>[:<port>]
    [4] path            An AMQP address path
    [5] operation       'send' or 'receive'
    [6] messages        Number of messages to transfer
    [7] bytes           Length of generated message body
    [8] credit          Amount of credit to maintain

### Output

Implementations must print sent transfers to standard output, one
transfer per line.

    <message-id>,<send-time>\n

Implementations must print received transfers to standard output, one
transfer per line.

    <message-id>,<send-time>,<receive-time>\n

Time values are unix epoch milliseconds.

    10,1472344673324,1472344673345

To avoid any performance impact, take care that writes to standard
output are buffered.

### Messages

Implementations must give each message a unique ID to aid debugging.
They must also set an application property named `SendTime` containing
a `long` representing the send time in milliseconds.

- XXX at-least-once, non-durable
