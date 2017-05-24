# Quiver

Tools for testing the performance of messaging clients and servers.

    [Start an AMQP server with a queue called 'q0']
    $ quiver q0
    ---------------------- Sender -----------------------  --------------------- Receiver ----------------------  --------
       T [s]      Count [m]  Rate [m/s]  CPU [%]  RSS [M]     T [s]      Count [m]  Rate [m/s]  CPU [%]  RSS [M]  Lat [ms]
    -----------------------------------------------------  -----------------------------------------------------  --------
         2.1         18,168       9,084       98     33.8       2.1         15,144       7,568      100     27.9       203
         4.1         36,395       9,104       96     33.8       4.1         31,046       7,943      100     27.9       460
         6.1         54,827       9,207       97     33.8       6.1         46,466       7,702      100     27.9       731
    [...]
           -              -           -        -        -     124.2        974,277       7,541      100     27.9    17,075
           -              -           -        -        -     126.2        989,959       7,833      100     27.9    17,520
           -              -           -        -        -     128.2      1,000,000       5,015       60      0.0    17,695
    --------------------------------------------------------------------------------
    Subject: qpid-proton-python //localhost:5672/q0 (/tmp/quiver-9rWyTd)
    Messages:                                       1,000,000 messages
    Body size:                                            100 bytes
    Credit window:                                      1,000 messages
    Duration:                                           127.3 s
    Sender rate:                                        9,133 messages/s
    Receiver rate:                                      7,859 messages/s
    End-to-end rate:                                    7,857 messages/s
    Average latency:                                  9,056.9 ms
    Latency 25, 50, 75, 100%:        4375, 9187, 13578, 17777 ms
    Latency 99, 99.9, 99.99%:             17623, 17750, 17770 ms
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

| Name                  | Debian package        | Fedora package
| --------------------- | --------------------- | ---
| GCC C++               | build-essential       | gcc-c++
| GNU Make              | make                  | make
| Java 8 JDK            | openjdk-8-jdk         | java-1.8.0-openjdk-devel
| Maven                 | maven                 | maven
| Node.js               | nodejs*               | nodejs
| NumPy                 | python-numpy          | numpy
| Python 2.7            | python                | python
| Qpid Messaging C++    | libqpidmessaging2-dev, libqpidtypes1-dev, libqpidcommon2-dev | qpid-cpp-client-devel
| Qpid Messaging Python | python-qpid-messaging | python-qpid-messaging
| Qpid Proton C         | libqpid-proton8-dev   | qpid-proton-c-devel
| Qpid Proton C++       | -                     | qpid-proton-cpp-devel
| Qpid Proton Python    | python-qpid-proton    | python-qpid-proton
| XZ                    | xz-utils              | xz

\* On Debian you will also need to symlink `/usr/bin/nodejs` to
`/usr/bin/node`.

### Using Fedora packages

    $ sudo dnf enable jross/ssorj
    $ sudo dnf install quiver

If you don't have `dnf`, use the repo files at
<https://copr.fedorainfracloud.org/coprs/jross/ssorj/>.

### Installing from source

By default, installs from source go to `/usr/local`.  Make sure
`/usr/local/bin` is in your path.

    $ cd quiver/
    $ sudo make install

## Development

To setup paths in your development environment, source the `devel.sh`
script from the project directory.

    $ cd quiver/
    $ source devel.sh

The `devel` make target creates a local installation in your checkout
and runs a sanity test.

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

### Building against locally installed libraries

To alter the GCC library and header search paths, use the
`LIBRARY_PATH`, `C_INCLUDE_PATH`, and`CPLUS_INCLUDE_PATH` environment
variables.

    $ export LIBRARY_PATH=$HOME/.local/lib64
    $ export C_INCLUDE_PATH=$HOME/.local/include
    $ export CPLUS_INCLUDE_PATH=$HOME/.local/include
    $ make clean devel

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

## Implementations

The `quiver-arrow` command is a wrapper that invokes one of several
implementation executables.
[More about implementations](docs/implementations.md).

## OpenShift

A docker image and OpenShift Container Platform (OCP) template are
provided under the openshift directory.  The
'openshift-support-template.yml' template provides a BuildConfig which
allows you to build from source.

To deploy this template, you can run the below:

    oc process -f openshift/openshift-support-template.yml | oc create -f -
    
The second template, 'openshift-pod-template.yml', deploys a runnable
quiver. It requires several parameters to run correctly:

 - DOCKER_IMAGE - the location of the fully qualified docker pull URL
 - DOCKER_CMD - the quiver command, in JSON array format, you want to execute

For example:

    oc process -f openshift/openshift-pod-template.yml \
        DOCKER_IMAGE=172.30.235.81:5000/test/quiver:latest \
        DOCKER_CMD="[\"quiver\", \"//172.17.0.7:5673/jobs/test\", \"--verbose\"]" \
        | oc create -f -
