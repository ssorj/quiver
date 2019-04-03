# Quiver

[![Build Status](https://travis-ci.org/ssorj/quiver.svg?branch=master)](https://travis-ci.org/ssorj/quiver)

Tools for testing the performance of messaging clients and servers.

    $ quiver --duration 10 --peer-to-peer q0
    ---------------------- Sender -----------------------  --------------------- Receiver ----------------------  --------
    Time [s]      Count [m]  Rate [m/s]  CPU [%]  RSS [M]  Time [s]      Count [m]  Rate [m/s]  CPU [%]  RSS [M]  Lat [ms]
    -----------------------------------------------------  -----------------------------------------------------  --------
         2.3      1,202,970     600,884      188     22.2       2.1      1,210,056     604,726      188      5.5         1
         5.2      1,791,304     209,297       67     27.2       5.4      1,982,039     237,241       68      5.5         1
         7.2      2,420,785     314,583      102     32.7       7.8      2,690,078     291,134       88      5.5         1
        11.2      3,032,565      16,826        4      0.0      10.1      3,032,565     146,237       38      0.0         1

    CONFIGURATION

    Sender ........................................ qpid-proton-c
    Receiver ...................................... qpid-proton-c
    Address URL .............................................. q0
    Output files ........................... /tmp/quiver-ljt_ztl1
    Duration ................................................. 10 seconds
    Body size ............................................... 100 bytes
    Credit window ......................................... 1,000 messages
    Flags .......................................... peer-to-peer

    RESULTS

    Count ............................................. 3,032,565 messages
    Duration ................................................ 9.8 seconds
    Sender rate ......................................... 310,586 messages/s
    Receiver rate ....................................... 310,618 messages/s
    End-to-end rate ..................................... 310,427 messages/s

    Latencies by percentile:

              0% ........ 1 ms       90.00% ........ 2 ms
             25% ........ 2 ms       99.00% ........ 3 ms
             50% ........ 2 ms       99.90% ........ 6 ms
            100% ........ 7 ms       99.99% ........ 6 ms

## Overview

Quiver arrow implementations are native clients (and sometimes also
servers) in various languages and APIs that either send or receive
messages and write raw information about the transfers to standard
output.  They are deliberately simple.

The `quiver-arrow` command runs a single implementation in send or
receive mode and captures its output.  It has options for defining the
execution parameters, selecting the implementation, and reporting
statistics.

The `quiver` command launches a pair of `quiver-arrow` instances, one
sender and one receiver, and produces a summary of the end-to-end
transmission of messages.

Some client quiver arrows can authenticate to their peer using username
password or a client certificate.

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
| Openssl               | openssl               | openssl
| Python 2.7            | python                | python
| Python 3              | python3               | python3
| Qpid Messaging C++    | libqpidmessaging-dev, libqpidtypes-dev, libqpidcommon-dev | qpid-cpp-client-devel
| Qpid Messaging Python | python-qpid-messaging, python-qpid | python-qpid-messaging
| Qpid Proton C         | libqpid-proton-proactor1-dev | qpid-proton-c-devel
| Qpid Proton C++       | libqpid-proton-cpp11-dev | qpid-proton-cpp-devel
| Qpid Proton Python    | python3-qpid-proton   | python3-qpid-proton
| SASL                  | cyrus-sasl-devel cyrus-sasl-plain cyrus-sasl-md5 | libsasl2-2 libsasl2-dev libsasl2-modules sasl2-bin
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

Quiver requires newer versions of the Qpid dependencies than Ubuntu
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
        openssl unzip xz-utils

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

    usage: quiver [-h] [--output DIR] [--arrow IMPL] [--sender IMPL] [--receiver IMPL] [--impl IMPL] [--peer-to-peer] [-c COUNT] [-d DURATION]
                  [--body-size COUNT] [--credit COUNT] [--transaction-size COUNT] [--durable] [--timeout DURATION] [--quiet] [--verbose]
                  [--init-only] [--version]
                  ADDRESS-URL

    Start a sender-receiver pair for a particular messaging address.

    'quiver' is one of the Quiver tools for testing the performance of
    message servers and APIs.

    positional arguments:
      ADDRESS-URL           The location of a message source or target

    optional arguments:
      -h, --help            show this help message and exit
      --output DIR          Save output files to DIR
      --arrow IMPL          Use IMPL to send and receive (default qpid-proton-c)
      --sender IMPL         Use IMPL to send (default qpid-proton-c)
      --receiver IMPL       Use IMPL to receive (default qpid-proton-c)
      --impl IMPL           An alias for --arrow
      --peer-to-peer        Connect the sender directly to the receiver in server
                            mode
      --cert CERT.PEM       Certificate filename - used for client authentication
      --key PRIVATE-KEY.PEM
                            Private key filename - - used for client
                            authentication
      -c COUNT, --count COUNT
                            Send or receive COUNT messages (default 1m; 0 means no
                            limit)
      -d DURATION, --duration DURATION
                            Stop after DURATION, ignoring --count (default 0,
                            disabled)
      --body-size COUNT     Send message bodies containing COUNT bytes (default
                            100)
      --credit COUNT        Sustain credit for COUNT incoming messages (default
                            1000)
      --transaction-size COUNT
                            Transfer batches of COUNT messages inside transactions
                            (default 0, disabled)
      --durable             Require persistent store-and-forward transfers
      --timeout DURATION    Fail after DURATION without transfers (default 10s)
      --quiet               Print nothing to the console
      --verbose             Print details to the console
      --init-only           Initialize and exit
      --version             Print the version and exit

    address URLs:
      [SCHEME:][//SERVER/]ADDRESS     The default server is 'localhost'
      queue0
      //localhost/queue0
      amqp://example.net:10000/jobs
      amqps://10.0.0.10/jobs/alpha
      amqps://user:password&10.0.0.10/jobs/alpha

    count format:                     duration format:
      1 (no unit)    1                  1 (no unit)    1 second
      1k             1,000              1s             1 second
      1m             1,000,000          1m             1 minute
                                        1h             1 hour

    arrow implementations:
      activemq-artemis-jms            Client mode only; requires Artemis server
      activemq-jms                    Client mode only; ActiveMQ or Artemis server
      qpid-jms (jms)                  Client mode only
      qpid-messaging-cpp              Client mode only
      qpid-messaging-python           Client mode only
      qpid-proton-c (c)               The default implementation
      qpid-proton-cpp (cpp)
      qpid-proton-python (python, py)
      rhea (javascript, js)
      vertx-proton (java)             Client mode only

    example usage:
      $ qdrouterd &                   # Start a message server
      $ quiver q0                     # Start the test

### `quiver-arrow`

This command sends or receives AMQP messages as fast as it can.  Each
invocation creates a single connection.  It terminates when the target
number of messages are all sent or received.

    usage: quiver-arrow [-h] [--output DIR] [--impl NAME] [--info] [--id ID]
                        [--server] [--passive] [--prelude PRELUDE]
                        [--cert CERT.PEM] [--key PRIVATE-KEY.PEM] [-c COUNT]
                        [-d DURATION] [--body-size COUNT] [--credit COUNT]
                        [--transaction-size COUNT] [--durable]
                        [--timeout DURATION] [--quiet] [--verbose] [--init-only]
                        [--version]
                        OPERATION ADDRESS-URL

### `quiver-server`

This command starts a server implementation and configures it to serve
the given address.

    usage: quiver-server [-h] [--impl NAME] [--info] [--ready-file FILE] [--prelude PRELUDE] [--quiet] [--verbose]
                         [--init-only] [--version] ADDRESS-URL

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

    $ quiver --peer-to-peer --sender qpid-jms --receiver qpid-proton-python q0

## More information

 - [Implementations](impls/README.md)
 - [Packaging](packaging/README.md)
