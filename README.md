# Quiver

A tool for testing the performance of AMQP servers and messaging APIs.

    [Start an AMQP server]
    $ quiver receive q0 &
    $ quiver send q0
    *     10,000    3,271 transfers/s
    [...]
    *    100,000    3,932 transfers/s
    --------------------------------------------------------------------------------
    Duration:                                            26.1 s
    Transfer count:                                   100,000 transfers
    Transfer rate:                                      3,826 transfers/s
    Latency (min, max, avg):                 11.0, 47.4, 19.5 ms
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

    usage: quiver [-h] [-n COUNT] [-v] [--impl NAME] [--bytes COUNT]
                  [--credit COUNT] [--timeout SECONDS] [--server]
                  [--output DIRECTORY] [--quiet]
                  OPERATION ADDRESS

    Test the performance of AMQP servers and messaging APIs

    positional arguments:
      OPERATION             Either 'send' or 'receive'
      ADDRESS               The location of an AMQP node

    optional arguments:
      -h, --help            show this help message and exit
      -n COUNT, --messages COUNT
                            Send or receive COUNT messages (default: 100000)
      -v, --verbose         Periodically print status to the console (default: False)
      --impl NAME           Use NAME implementation (default: proton-python)
      --bytes COUNT         Send message bodies containing COUNT bytes (default: 1000)
      --credit COUNT        Sustain credit for COUNT incoming transfers (default: 100)
      --timeout SECONDS     Fail after SECONDS without transfers (default: 10)
      --server              Operate in server mode (default: False)
      --output DIRECTORY    Save output files to DIRECTORY (default: None)
      --quiet               Print nothing to the console (default: False)

    operations:
      send                  Send messages
      receive               Receive messages

    addresses:
      [//DOMAIN/]PATH              The default domain is 'localhost:5672'
      //example.net/jobs
      //10.0.0.10:5672/jobs/alpha
      //localhost/q0
      q0

    implementations:
      proton-python
      qpid-messaging-python        Supports client mode only

## Examples

### Running Quiver with Dispatch Router

    $ qdrouterd &
    $ quiver receive q0 &
    $ quiver send q0

### Running Quiver with Artemis

    [Configure Artemis with queue q0]
    $ <instance-dir>/bin/artemis run
    $ quiver receive q0 &
    $ quiver send q0
    
### Running Quiver with the Qpid C++ broker

    $ qpidd --auth no &
    $ qpid-config add queue q0
    $ quiver receive q0 &
    $ quiver send q0

### Running Quiver peer-to-peer

    $ quiver --server receive q0 &
    $ quiver send q0

    [or]

    $ quiver --server send q0 &
    $ quiver receive q0

## Implementations

The `quiver` command is a wrapper that invokes an implementation
executable using standard arguments.  `quiver` tries to take
responsibility for 'cooking' its inputs so implementations can focus
on mechanics.  By the same token, implementation outputs are
intentionally left raw so `quiver` can do the work of presenting the
results.

### Input

Implementations must process the following positional arguments.

    [1] output-dir      A directory for output files
    [2] mode            'client' or 'server'
    [3] operation       'send' or 'receive'
    [4] domain          <host>[:<port>]
    [5] path            An AMQP address path
    [6] messages        Number of messages to transfer
    [7] bytes           Length of generated message body
    [8] credit          Amount of credit to maintain
    [9] timeout         Timeout in seconds

### Output

Implementations must print received transfers to standard output, one
transfer per line.

    <message-id>,<send-time>,<receive-time>\r\n

Time values are unix epoch seconds, with at least nine digits of
sub-second precision.

    10,1472344673.324439049,1472344673.345107079

## Todo

- Provide aliases for frequently used impls
- Save periodic memory and CPU usage
