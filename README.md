# Quiver

Tools for testing the performance of messaging clients and servers.

    [Start an AMQP server with a queue called 'q0']
    $ quiver q0
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

Quiver arrow implementations are native clients (and sometimes also
servers) in various languages and APIs that send or receive messages
and write raw information about the transfers to standard output.
They are deliberately simple.

The `quiver-arrow` command runs an implementation in send or receive
mode and captures its output.  It has options for defining the
execution parameters, selecting the implementation, and reporting
statistics.

The `quiver` command makes it easy to launch `quiver-arrow` instances.
In the future, it will collate the results from the individual
`quiver-arrow` runs and produce a consolidated report.

## Installation

### Dependencies

    NAME                     FEDORA PACKAGES
    ------------------------ --------------------------------------------
    Java 8                   java-1.8.0-openjdk, java-1.8.0-openjdk-devel
    Maven                    maven
    GNU Make                 make
    Node.js                  nodejs
    NumPy                    numpy
    Python 2.7               python
    Qpid Messaging Python    python-qpid-messaging
    Qpid Proton Python       python-qpid-proton
    Qpid Messaging C++       qpid-cpp-client, qpid-cpp-client-devel
    Qpid Proton C            qpid-proton-c, qpid-proton-c-devel
    XZ                       xc
    GCC C++ compiler         gcc-c++

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

### Project layout

    devel.sh              # Sets up your project environment for development
    Makefile              # Defines the build and test targets
    bin/                  # Command-line tools
    exec/                 # Library executables and quiver-arrow implementations
    scripts/              # Scripts called by Makefile rules
    docs/                 # Documentation and notes
    java/                 # Java library code
    javascript/           # JavaScript library code
    python/               # Python library code
    build/                # The default build location
    install/              # The development-mode install location

### Make targets

In the development environment, most things are accomplished by
running make targets.  These are the important ones:

    $ make build         # Builds the code
    $ make install       # Installs the code
    $ make clean         # Removes build/ and install/
    $ make devel         # Builds, installs in the checkout, tests sanity
    $ make test          # Runs the test suite

To alter the GCC library and header search paths, use the
`LIBRARY_PATH` and `C_INCLUDE_PATH` or `CPLUS_INCLUDE_PATH`
environment variables.

    $ export LIBRARY_PATH=~/.local/lib
    $ export CPLUS_INCLUDE_PATH=~/.local/include
    $ make clean devel

Set `LD_LIBRARY_PATH` or update `ld.so.conf` to match your
`LIBRARY_PATH` before running the resulting executables.

## Command-line interface

### `quiver`

This command starts sender-receiver pairs.  By default it creates a
single pair.  Each sender or receiver is an invocation of the
`quiver-arrow` command.

    usage: quiver [-h] [-m COUNT] [--impl NAME] [--server] [--bytes COUNT] [--credit COUNT]
                  [--timeout SECONDS] [--output DIRECTORY] [--quiet] [--verbose]
                  ADDRESS

    Test the performance of messaging clients and servers

    positional arguments:
      ADDRESS               The location of a message queue

    optional arguments:
      -h, --help            show this help message and exit
      -m COUNT, --messages COUNT
                            Send or receive COUNT messages (default: 1m)
      --impl NAME           Use NAME implementation (default: qpid-proton-python)
      --server              Operate in server mode (default: False)
      --bytes COUNT         Send message bodies containing COUNT bytes (default: 100)
      --credit COUNT        Sustain credit for COUNT incoming transfers (default: 1k)
      --timeout SECONDS     Fail after SECONDS without transfers (default: 10)
      --output DIRECTORY    Save output files to DIRECTORY (default: None)
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
      qpid-proton-python [python]
      rhea [javascript]               Client mode only at the moment
      vertx-proton                    Client mode only

### `quiver-arrow`

This command sends or receives AMQP messages as fast as it can.  Each
invocation creates a single connection.  It terminates when the target
number of messages are all sent or received.

    usage: quiver-arrow [-h] [-m COUNT] [--impl NAME] [--server] [--bytes COUNT] [--credit COUNT]
                        [--timeout SECONDS] [--output DIRECTORY] [--quiet] [--verbose]
                        OPERATION ADDRESS

    Send or receive messages

    positional arguments:
      OPERATION             Either 'send' or 'receive'
      ADDRESS               The location of a message queue

    optional arguments:
      -h, --help            show this help message and exit
      -m COUNT, --messages COUNT
                            Send or receive COUNT messages (default: 1m)
      --impl NAME           Use NAME implementation (default: qpid-proton-python)
      --server              Operate in server mode (default: False)
      --bytes COUNT         Send message bodies containing COUNT bytes (default: 100)
      --credit COUNT        Sustain credit for COUNT incoming transfers (default: 1k)
      --timeout SECONDS     Fail after SECONDS without transfers (default: 10)
      --output DIRECTORY    Save output files to DIRECTORY (default: None)
      --quiet               Print nothing to the console (default: False)
      --verbose             Print details to the console (default: False)

    operations:
      send                  Send messages
      receive               Receive messages

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

    $ quiver-arrow --server receive q0 &
    $ quiver-arrow send q0

## Implementations

The `quiver-arrow` command is a wrapper that invokes one of several
implementation executables.
[More about implementations](docs/implementations.md).
