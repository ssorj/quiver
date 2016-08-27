# Quiver

Tools for testing the performance of AMQP servers and messaging APIs.

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

    usage: quiver [-h] [--impl NAME] [-n COUNT] [--bytes COUNT] [--credit COUNT]
        [--server] OPERATION URL

    Test the performance of AMQP servers and messaging APIs

    positional arguments:
      OPERATION             Either 'send' or 'receive'
      ADDRESS               The location of an AMQP node

    optional arguments:
      -h, --help            show this help message and exit
      --impl NAME           Use the NAME implementation (default: proton-python)
      -n COUNT, --messages  COUNT
                            Send or receive COUNT messages (default: 100000)
      --bytes COUNT         Send message bodies containing COUNT bytes (default: 1000)
      --credit COUNT        Sustain credit for COUNT incoming transfers (default: 100)
      --server              Operate in server mode (default: False)

    operations:
      send                  Send messages
      receive               Receive messages

    URLs:
      [//DOMAIN/]PATH
      //example.net/jobs
      //10.0.0.100:5672/jobs/alpha
      //localhost/q0
      q0

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

### Positional arguments

Implementations must process these arguments.

    [1] output-dir      A temporary work directory
    [2] mode            'client' or 'server'
    [3] operation       'send' or 'receive'
    [4] domain          <host>[:<port>]
    [5] path            An AMQP address path
    [6] messages        Number of transfers
    [7] bytes           Length of generated message body
    [8] credit          Credit to maintain

### Recording transfers

Implementations must save received transfers to
`<output-dir>/transfers.csv` in the following record format, one
transfer per line.

    <message-id>,<send-time>,<receive-time>\r\n

## Todo

- Consider periodic transfer data saves - period on time or messages?
- Offer aliases for frequently used impls
- Send-and-receive operation
- Save rusage info
