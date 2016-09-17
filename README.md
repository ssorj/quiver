# Quiver

Tools for testing the performance of messaging clients and servers.

    [Start an AMQP server]
    $ quiver q0 receive &
    $ quiver q0 send
    *        6,320        6,402 transfers/s         131.2 ms avg latency
    *       12,942        5,206 transfers/s         382.5 ms avg latency
    [...]
    *       86,963        1,791 transfers/s       2,887.0 ms avg latency
    *       93,984        1,743 transfers/s       3,091.8 ms avg latency
    --------------------------------------------------------------------------------
    Duration:                                            15.1 s
    Transfer count:                                   100,000 transfers
    Transfer rate:                                      6,604 transfers/s
    Latency (min, max, avg):            7.0, 3,345.7, 1,768.4 ms
    --------------------------------------------------------------------------------

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

## Command-line interface

### quiver

`quiver` is the main entry point.  It sends and receives AMQP messages
as fast as it can.  When the requested transfers are done, it reports
the throughput and latency of the overall set, from the first send to
the last receive.

    usage: quiver [-h] [-n COUNT] [-v] [--impl NAME] [--bytes COUNT] [--credit COUNT]
                  [--timeout SECONDS] [--server] [--output DIRECTORY] [--quiet]
                  ADDRESS OPERATION

    Test the performance of AMQP servers and messaging APIs

    positional arguments:
      ADDRESS               The location of an AMQP node
      OPERATION             Either 'send' or 'receive'

    optional arguments:
      -h, --help            show this help message and exit
      -n COUNT, --messages COUNT
                            Send or receive COUNT messages (default: 1000000)
      -v, --verbose         Periodically print status to the console (default: False)
      --impl NAME           Use NAME implementation (default: qpid-proton-python)
      --bytes COUNT         Send message bodies containing COUNT bytes (default: 100)
      --credit COUNT        Sustain credit for COUNT incoming transfers (default: 1000)
      --timeout SECONDS     Fail after SECONDS without transfers (default: 10)
      --server              Operate in server mode (default: False)
      --output DIRECTORY    Save output files to DIRECTORY (default: None)
      --quiet               Print nothing to the console (default: False)

    operations:
      send                  Send messages
      receive               Receive messages

    addresses:
      [//DOMAIN/]PATH                 The default domain is 'localhost:5672'
      //example.net/jobs
      //10.0.0.10:5672/jobs/alpha
      //localhost/q0
      q0

    implementations:
      qpid-jms (jms)                  Supports client mode only
      qpid-messaging-cpp              Supports client mode only
      qpid-messaging-python           Supports client mode only
      qpid-proton-python (python)

### quiver-launch

`quiver-launch` starts sender-receiver pairs.  Each sender or receiver
is an invocation of the `quiver` command.  Arguments not processed by
`quiver-launch` are passed to `quiver`.

    usage: quiver-launch [-h] [--pairs COUNT] [--senders COUNT]
                         [--receivers COUNT] ADDRESS

    Launch quiver senders and receivers

    Arguments not processed by quiver-launch are passed to
    the 'quiver' command

    positional arguments:
      ADDRESS            The location of an AMQP node

    optional arguments:
      -h, --help         show this help message and exit
      --pairs COUNT      Launch COUNT sender-receiver pairs (default: 1)
      --senders COUNT    Launch COUNT senders (default: 1)
      --receivers COUNT  Launch COUNT receivers (default: 1)

## Examples

### Running Quiver with Dispatch Router

    $ qdrouterd &
    $ quiver q0 receive &
    $ quiver q0 send

### Running Quiver with Artemis

    $ <instance-dir>/bin/artemis run &
    $ <instance-dir>/bin/artemis destination create --name q0 --type core-queue
    $ quiver q0 receive &
    $ quiver q0 send
    
### Running Quiver with the Qpid C++ broker

    $ qpidd --auth no &
    $ qpid-config add queue q0
    $ quiver q0 receive &
    $ quiver q0 send

### Running Quiver peer-to-peer

    $ quiver --server q0 receive &
    $ quiver q0 send

    [or]

    $ quiver --server q0 send &
    $ quiver q0 receive

## Implementations

The `quiver` command is a wrapper that invokes an implementation
executable using standard arguments.  `quiver` tries to take
responsibility for "cooking" its inputs so implementations can focus
on mechanics.  By the same token, implementation outputs are
intentionally left raw so `quiver` can do the work of presenting the
results.

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

## Todo

- Save periodic memory and CPU usage
