# Quiver

[![Build Status](https://travis-ci.org/ssorj/quiver.svg?branch=master)](https://travis-ci.org/ssorj/quiver)

Tools for testing the performance of messaging clients and servers.

    [Start an AMQP server with a queue called 'q0']
    $ quiver q0
    ---------------------- Sender -----------------------  --------------------- Receiver ----------------------  --------
    Time [s]      Count [m]  Rate [m/s]  CPU [%]  RSS [M]  Time [s]      Count [m]  Rate [m/s]  CPU [%]  RSS [M]  Lat [ms]
    -----------------------------------------------------  -----------------------------------------------------  --------
         2.1         16,529       8,256       89     37.6       2.1         15,746       7,865       98     31.8       112
         4.1         32,504       7,984       87     37.6       4.1         31,769       8,003       99     31.8       116
    [...]
       122.2        988,135       8,476       90     38.2     122.2        987,384       8,534       99     31.8       109
       124.2      1,000,000       5,927       65      0.0     124.2      1,000,000       6,302       75      0.0       111
    --------------------------------------------------------------------------------
    Subject: qpid-proton-python //localhost:5672/q0 (/tmp/quiver-9rWyTd)
    Messages:                                       1,000,000 messages
    Body size:                                            100 bytes
    Credit window:                                      1,000 messages
    Duration:                                           123.6 s
    Sender rate:                                        8,099 messages/s
    Receiver rate:                                      8,096 messages/s
    End-to-end rate:                                    8,092 messages/s
    Latency:
      Average:                                          115.1 ms
      Min:                                                 63 ms
      50%:                                                112 ms
      90%:                                                126 ms
      99%:                                                157 ms
      99.9%:                                              196 ms
      99.99%:                                             223 ms
      99.999%:                                            227 ms
      Max:                                                228 ms
    --------------------------------------------------------------------------------

## Overview

Quiver implementations are native clients (and sometimes also servers)
in various languages and APIs that either send or receive messages and
write raw information about the transfers to standard output.  They
are deliberately simple.

The `quiver-arrow` command runs a single implementation in send or
receive mode and captures its output.  It has options for defining the
execution parameters, selecting the implementation, and reporting
statistics.

The `quiver` command launches a pair of `quiver-arrow` instances, one
sender and one receiver, and produces a summary of the end-to-end
transmission of messages.

## Installation

### Dependencies

| Name                  | Ubuntu packages       | Fedora packages
| --------------------- | --------------------- | ---
| GCC C++               | build-essential       | gcc-c++
| GNU Make              | make                  | make
| Java 8 JDK            | openjdk-8-jdk         | java-1.8.0-openjdk-devel
| Maven                 | maven                 | maven
| Node.js               | nodejs                | nodejs
| NumPy                 | python-numpy, python3-numpy | python-numpy, python3-numpy
| Python 2.7            | python                | python
| Python 3              | python3               | python3
| Qpid Messaging C++    | libqpidmessaging-dev, libqpidtypes-dev, libqpidcommon-dev | qpid-cpp-client-devel
| Qpid Messaging Python | python-qpid-messaging, python-qpid | python-qpid-messaging
| Qpid Proton C         | libqpid-proton-proactor1-dev | qpid-proton-c-devel
| Qpid Proton C++       | libqpid-proton-cpp11-dev | qpid-proton-cpp-devel
| Qpid Proton Python    | python3-qpid-proton   | python3-qpid-proton
| Unzip                 | unzip                 | unzip
| XZ                    | xz-utils              | xz

### Using Docker

    $ sudo docker run -it ssorj/quiver

### Installing on Fedora

    $ sudo dnf install dnf-plugins-core
    $ sudo dnf enable jross/ssorj
    $ sudo dnf install quiver

If you don't have `dnf`, use the repo files at
<https://copr.fedorainfracloud.org/coprs/jross/ssorj/>.

### Installing on Ubuntu

Quiver requires newer version of the Qpid dependencies than Ubuntu
provides by default.  Use these commands to install them from an
Ubuntu PPA.

    $ sudo apt-get install software-properties-common
    $ sudo add-apt-repository ppa:qpid/released
    $ sudo apt-get update
    $ sudo apt-get install build-essential make openjdk-8-jdk maven nodejs \
        python python-numpy python3 python3-numpy \
        libqpidmessaging-dev libqpidtypes-dev libqpidcommon-dev \
        libqpid-proton-proactor1-dev libqpid-proton-cpp11-dev \
        python-qpid python-qpid-messaging python3-qpid-proton \
        unzip xz-utils

After this you can install from source.

To use the JavaScript implementation, you also need to symlink
`nodejs` to `node`.

    $ cd /usr/local/bin && sudo ln -s ../../bin/nodejs node

### Installing from source

By default, installs from source go to `/usr/local`.  Make sure
`/usr/local/bin` is in your path.

    $ cd quiver/
    $ make build
    $ sudo make install

Use the `PREFIX` option to change the install location.

    $ make build PREFIX=/usr
    $ sudo make install

## Development

To setup paths in your development environment, source the `devel.sh`
script from the project directory.

    $ cd quiver/
    $ source devel.sh

### Project layout

    devel.sh              # Sets up your project environment for development
    Makefile              # Defines the build and test targets
    bin/                  # Command-line tools
    impls/                # Arrow and server implementations
    scripts/              # Scripts called by Makefile rules
    docs/                 # Documentation and notes
    java/                 # Java library code
    javascript/           # JavaScript library code
    python/               # Python library code
    build/                # The default build location

### Make targets

In the development environment, most things are accomplished by
running make targets.  These are the important ones:

    $ make build         # Builds the code
    $ make install       # Installs the code
    $ make clean         # Removes build/
    $ make test          # Runs the test suite

### Building against locally installed libraries

To alter the GCC library and header search paths, use the
`LIBRARY_PATH`, `C_INCLUDE_PATH`, and`CPLUS_INCLUDE_PATH` environment
variables.

    $ export LIBRARY_PATH=$HOME/.local/lib64
    $ export C_INCLUDE_PATH=$HOME/.local/include
    $ export CPLUS_INCLUDE_PATH=$HOME/.local/include
    $ make clean build

Set `LD_LIBRARY_PATH` or update `ld.so.conf` to match your
`LIBRARY_PATH` before running the resulting executables.

    $ export LD_LIBRARY_PATH=$HOME/.local/lib64

Source `misc/local-libs-env.sh` in your shell to set these variables
for libraries under `$HOME/.local` and `/usr/local`.

## Command-line interface

### `quiver`

This command starts a sender-receiver pair.  Each sender or receiver
is an invocation of the `quiver-arrow` command.

    usage: quiver [-h] [-m COUNT] [--impl NAME] [--body-size COUNT] [--credit COUNT]
                  [--timeout SECONDS] [--output DIRECTORY] [--init-only] [--quiet]
                  [--verbose] ADDRESS

    Start a sender-receiver pair for a particular messaging address.

    'quiver' is one of the Quiver tools for testing the performance of
    message servers and APIs.

    positional arguments:
      ADDRESS               The location of a message queue

    optional arguments:
      -h, --help            show this help message and exit
      -m COUNT, --messages COUNT
                            Send or receive COUNT messages (default: 1m)
      --impl NAME           Use NAME implementation (default: qpid-proton-python)
      --body-size COUNT     Send message bodies containing COUNT bytes (default: 100)
      --credit COUNT        Sustain credit for COUNT incoming transfers (default: 1k)
      --timeout SECONDS     Fail after SECONDS without transfers (default: 10)
      --output DIRECTORY    Save output files to DIRECTORY (default: None)
      --init-only           Initialize and immediately exit (default: False)
      --quiet               Print nothing to the console (default: False)
      --verbose             Print details to the console (default: False)

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
      qpid-proton-cpp [cpp]
      qpid-proton-python [python]
      rhea [javascript]
      vertx-proton [java]             Client mode only

### `quiver-arrow`

This command sends or receives AMQP messages as fast as it can.  Each
invocation creates a single connection.  It terminates when the target
number of messages are all sent or received.

    usage: quiver-arrow [-h] [-m COUNT] [--impl NAME] [--body-size COUNT] [--credit COUNT]
                        [--timeout SECONDS] [--output DIRECTORY] [--init-only] [--quiet]
                        [--verbose] [--id ID] [--server] [--passive]
                        OPERATION ADDRESS

    Send or receive a set number of messages as fast as possible using a
    single connection.

    'quiver-arrow' is one of the Quiver tools for testing the performance
    of message servers and APIs.

    positional arguments:
      OPERATION             Either 'send' or 'receive'
      ADDRESS               The location of a message queue

    optional arguments:
      -h, --help            show this help message and exit
      --id ID               Use ID as the client or server identity (default: None)
      --server              Operate in server mode (default: False)
      --passive             Operate in passive mode (default: False)
      -m COUNT, --messages COUNT
                            Send or receive COUNT messages (default: 1m)
      --impl NAME           Use NAME implementation (default: qpid-proton-python)
      --body-size COUNT     Send message bodies containing COUNT bytes (default: 100)
      --credit COUNT        Sustain credit for COUNT incoming transfers (default: 1k)
      --timeout SECONDS     Fail after SECONDS without transfers (default: 10)
      --output DIRECTORY    Save output files to DIRECTORY (default: None)
      --init-only           Initialize and immediately exit (default: False)
      --quiet               Print nothing to the console (default: False)
      --verbose             Print details to the console (default: False)

    operations:
      send                  Send messages
      receive               Receive messages

    server and passive modes:
      By default quiver-arrow operates in client and active modes, meaning
      that it creates an outbound connection to a server and actively
      initiates creation of the protocol entities (sessions and links)
      required for communication.  The --server option tells quiver-arrow
      to instead listen for and accept incoming connections.  The
      --passive option tells it to receive and confirm incoming requests
      for new protocol entities but not to create them itself.

## Examples

### Running Quiver with ActiveMQ

    [Configure ActiveMQ for anonymous connections and AMQP]
    $ <instance-dir>/bin/activemq start
    $ quiver q0

### Running Quiver with ActiveMQ Artemis

    $ <instance-dir>/bin/artemis run &
    $ <instance-dir>/bin/artemis destination create --name q0 --type core-queue
    $ quiver q0

### Running Quiver with the Qpid C++ broker

    $ qpidd --auth no &
    $ qpid-config add queue q0
    $ quiver q0

### Running Quiver with the Qpid Dispatch router

    $ qdrouterd &
    $ quiver q0

### Running Quiver peer-to-peer

    $ quiver --peer-to-peer --sender qpid-jms --receiver qpid-proton-python

## More information

 - [Implementations](impls/README.md)
 - [Packaging](packaging/README.md)
