# Quiver

[![main](https://github.com/ssorj/quiver/actions/workflows/main.yaml/badge.svg?branch=main)](https://github.com/ssorj/quiver/actions/workflows/main.yaml?query=branch%3Amain)

Tools for testing the performance of messaging clients and servers.

~~~
$ quiver
---------------------- Sender -----------------------  --------------------- Receiver ----------------------  --------
Time [s]      Count [m]  Rate [m/s]  CPU [%]  RSS [M]  Time [s]      Count [m]  Rate [m/s]  CPU [%]  RSS [M]  Lat [ms]
-----------------------------------------------------  -----------------------------------------------------  --------
     2.2      2,495,486   1,246,497       82     11.4       2.1      2,367,633   1,183,225       89     10.2         0
     4.2      4,870,652   1,186,990       77     12.2       4.1      4,751,211   1,191,193       88     10.7         0
     6.2      7,244,794   1,186,478       77     12.2       6.1      7,123,233   1,185,418       89     10.7         0
     8.2      9,621,240   1,187,629       77     12.2       8.1      9,498,473   1,187,026       88     10.7         0
    10.2     11,757,474   1,067,583       70      0.0      10.1     11,756,478   1,128,438       84      0.0         0

CONFIGURATION

Sender ........................................ qpid-proton-c
Receiver ...................................... qpid-proton-c
URL ........................... amqp://localhost:56727/quiver
Output files ........................... /tmp/quiver-mv9r_g7t
Duration ................................................. 10 seconds
Body size ............................................... 100 bytes
Credit window ......................................... 1,000 messages

RESULTS

Count ............................................ 11,756,484 messages
Duration ................................................ 9.9 seconds
Sender rate ....................................... 1,188,705 messages/s
Receiver rate ..................................... 1,188,845 messages/s
End-to-end rate ................................... 1,188,724 messages/s

Latencies by percentile:

          0% ........ 0 ms       90.00% ........ 1 ms
         25% ........ 0 ms       99.00% ........ 1 ms
         50% ........ 1 ms       99.90% ........ 1 ms
        100% ........ 2 ms       99.99% ........ 1 ms
~~~

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

Some client quiver arrows can authenticate to their peer using
username and password or a client certificate.

## Installation

### Dependencies

| Name                  | Ubuntu packages       | Fedora packages
| --------------------- | --------------------- | ---
| GCC C++               | build-essential       | gcc-c++
| GNU Make              | make                  | make
| Java 11 JDK           | openjdk-11-jdk        | java-11-openjdk-devel
| Maven                 | maven                 | maven
| Node.js               | nodejs                | nodejs
| NumPy                 | python-numpy, python3-numpy | python-numpy, python3-numpy
| OpenSSL               | openssl               | openssl
| Python 3              | python3               | python3
| Qpid Messaging C++    | libqpidmessaging-dev, libqpidtypes-dev, libqpidcommon-dev | qpid-cpp-client-devel
| Qpid Proton C         | libqpid-proton-proactor1-dev | qpid-proton-c-devel
| Qpid Proton C++       | libqpid-proton-cpp12-dev | qpid-proton-cpp-devel
| Qpid Proton Python    | python3-qpid-proton   | python3-qpid-proton
| SASL                  | libsasl2-2 libsasl2-dev libsasl2-modules sasl2-bin | cyrus-sasl-devel cyrus-sasl-plain cyrus-sasl-md5
| Unzip                 | unzip                 | unzip
| zstd                  | zstd                  | zstd

### Using Docker

    $ sudo docker run -it ssorj/quiver

### Installing on Ubuntu

Quiver requires newer versions of the Qpid dependencies than Ubuntu
provides by default.  Use these commands to install them from an
Ubuntu PPA.

    $ sudo apt-get install software-properties-common
    $ sudo add-apt-repository ppa:qpid/released
    $ sudo apt-get update
    $ sudo apt-get install build-essential make openjdk-11-jdk maven nodejs \
        python python-numpy python3 python3-numpy \
        libqpidmessaging-dev libqpidtypes-dev libqpidcommon-dev \
        libqpid-proton-proactor1-dev libqpid-proton-cpp12-dev \
        python-qpid python-qpid-messaging python3-qpid-proton \
        openssl unzip zstd

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

Source `scripts/home-local-libs-env.sh` or
`scripts/usr-local-libs-env.sh` in your shell to set these variables
for libraries under `$HOME/.local` or `/usr/local` respectively.

## Command-line interface

### `quiver`

This command starts a sender-receiver pair.  Each sender or receiver
is an invocation of the `quiver-arrow` command.

~~~
usage: quiver [-h] [--output DIR] [--impl IMPL] [--sender IMPL]
              [--receiver IMPL] [-d DURATION] [-c COUNT] [--rate COUNT]
              [--body-size COUNT] [--credit COUNT] [--transaction-size COUNT]
              [--durable] [--set-message-id] [--timeout DURATION] [--quiet]
              [--verbose] [--init-only] [--version] [--cert FILE] [--key FILE]
              [URL]

Start a sender-receiver pair for a particular messaging address.

'quiver' is one of the Quiver tools for testing the performance of
message servers and APIs.

positional arguments:
  URL                   The location of a message source or target (if not
                        set, quiver runs in peer-to-peer mode)

options:
  -h, --help            show this help message and exit
  --output DIR          Save output files to DIR
  --impl IMPL           Use IMPL to send and receive (default qpid-proton-c)
  --sender IMPL         Use IMPL to send (default qpid-proton-c)
  --receiver IMPL       Use IMPL to receive (default qpid-proton-c)
  -d DURATION, --duration DURATION
                        Stop after DURATION (default 30s)
  -c COUNT, --count COUNT
                        Send or receive COUNT messages (default 0, no limit)
  --rate COUNT          Target a rate of COUNT messages per second (default 0,
                        disabled)
  --body-size COUNT     Send message bodies containing COUNT bytes (default
                        100)
  --credit COUNT        Sustain credit for COUNT incoming messages (default
                        1000)
  --transaction-size COUNT
                        Transfer batches of COUNT messages inside transactions
                        (default 0, disabled)
  --durable             Require persistent store-and-forward transfers
  --set-message-id      Send each message with a message ID and read it on
                        receive
  --timeout DURATION    Fail after DURATION without transfers (default 10s)
  --quiet               Print nothing to the console
  --verbose             Print details to the console
  --init-only           Initialize and exit
  --version             Print the version and exit
  --cert FILE           The client TLS certificate file
  --key FILE            The client TLS private key file

URLs:
  [SCHEME:][//SERVER/]ADDRESS     The default server is 'localhost'
  queue0
  //localhost/queue0
  amqp://example.net:10000/jobs
  amqps://10.0.0.10/jobs/alpha
  amqps://username:password@10.0.0.10/jobs/alpha

count format:                     duration format:
  1 (no unit)    1                  1 (no unit)    1 second
  1k             1,000              1s             1 second
  1m             1,000,000          1m             1 minute
                                    1h             1 hour

arrow implementations:
  activemq-artemis-jms            Client mode only; requires Artemis server
  activemq-jms                    Client mode only; ActiveMQ or Artemis server
  qpid-jms (jms)                  Client mode only
  qpid-proton-c (c)               The default implementation
  qpid-proton-cpp (cpp)
  qpid-proton-python (python, py)
  qpid-protonj2 (java)            Client mode only
  qpid-proton-dotnet (.NET)       Client mode only
  rhea (javascript, js)
  vertx-proton (java)             Client mode only

example peer-to-peer usage:
  $ quiver                        # Run the test using the default C arrow

example client-server usage:
  $ qdrouterd &                   # Start a server listening on localhost
  $ quiver q0                     # Run the test
~~~

### `quiver-arrow`

This command sends or receives AMQP messages as fast as it can.  Each
invocation creates a single connection.  It terminates when the
requested duration is exceeded or the target number of messages are
all sent or received.

~~~
usage: quiver-arrow [-h] [--output DIR] [--impl IMPL] [--summary] [--info]
                    [--id ID] [--server] [--passive] [--prelude PRELUDE]
                    [-d DURATION] [-c COUNT] [--rate COUNT]
                    [--body-size COUNT] [--credit COUNT]
                    [--transaction-size COUNT] [--durable] [--set-message-id]
                    [--timeout DURATION] [--quiet] [--verbose] [--init-only]
                    [--version] [--cert FILE] [--key FILE]
                    OPERATION URL
~~~

### `quiver-server`

This command starts a server implementation and configures it to serve
the given address.

~~~
usage: quiver-server [-h] [--impl IMPL] [--info] [--ready-file FILE]
                     [--prelude PRELUDE] [--user USER] [--password SECRET]
                     [--cert FILE] [--key FILE] [--trust-store FILE] [--quiet]
                     [--verbose] [--init-only] [--version]
                     URL
~~~

## Examples

### Running Quiver with ActiveMQ Classic

Make sure you configure ActiveMQ to allow anonymous connections.

    $ <instance-dir>/bin/activemq start
    $ quiver q0

### Running Quiver with ActiveMQ Artemis

    $ <instance-dir>/bin/artemis run &
    $ <instance-dir>/bin/artemis queue create --name q0 --address q0 \
        --anycast --no-durable --auto-create-address --preserve-on-no-consumers
    $ quiver q0

### Running Quiver with Qpid Dispatch router

    $ qdrouterd &
    $ quiver q0

### Running Quiver peer-to-peer

    $ quiver
    $ quiver --sender qpid-jms
    $ quiver --sender rhea --receiver qpid-proton-python

## More information

 - [Implementations](impls/README.md)
 - [Packaging](packaging/README.md)
