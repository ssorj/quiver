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

    usage: quiver [-h] [--impl NAME] [-n COUNT] [--message FILE]
        [--connections COUNT] [--sessions COUNT] [--links COUNT] [--server]
        OPERATION URL

    Test the performance of AMQP servers and messaging APIs

    positional arguments:
      OPERATION             Either 'send' or 'receive'
      URL                   The location of an AMQP node

    optional arguments:
      -h, --help            show this help message and exit
      --impl NAME           Use the NAME implementation (default: proton-python)
      -n COUNT, --transfers COUNT
                            Send or receive COUNT messages (default: 100000)
      --message FILE        Send the message stored in FILE (default: None)
      --connections COUNT   Create COUNT connections (default: 1)
      --sessions COUNT      Create COUNT sessions (default: 1)
      --links COUNT         Create COUNT links (default: 1)
      --server              Operate in server mode (default: False)

    operations:
      send                  Send messages
      receive               Receive messages

    URLs:
      [HOST:PORT]/ADDRESS
      example.com/jobs
      example.com:5672/jobs
      10.0.0.101/jobs
      localhost:56720/q0
      q0

    implementations:
      proton-python
      qpid-messaging-python       Supports client mode only

### quiver-message

`quiver-message` creates AMQP message bytes for use by `quiver` via
its `--message` argument.  It's currently very basic.

    usage: quiver-message [-h] [--bytes COUNT] [-o FILE]

    Generate an AMQP message and store it in a file

    optional arguments:
      -h, --help            show this help message and exit
      --bytes COUNT         Create body with COUNT bytes (default: 1000)
      -o FILE, --output FILE
                            Save the message to FILE (default: None)

## Examples

### Running Quiver with Dispatch Router

    $ qdrouterd &
    $ quiver receive q0 &
    $ quiver send q0

### Running Quiver with Artemis

    [Configure artemis with queue q0]
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

    [1] work_dir        A temporary work directory
    [2] mode            'client' or 'server'
    [3] operation       'send' or 'receive'
    [4] host_port       <host>:<port>
    [5] address         An AMQP node address
    [6] transfers       An integral number of transfers

### Keyword arguments

Additional arguments are supplied as `<name>=<value>` pairs.  Some are
required for certain modes and operations.

    Mode 'client'       Requires connections=<n>, sessions=<n>, links=<n>
    Operation 'send'    Requires message=<file>

### Recording transfers

Implementations must save received transfers to
`<work-dir>/transfers.csv` in the following record format, one
transfer per line.

    <message-id>,<send-time>,<receive-time>\r\n

## Todo

- Use gnu style "--name value" options
- Consider periodic transfer data saves - period on time or messages?
- --message-body "" <-- 
- --entire-message-from-file <-- $(quiver-message)
  - Means somewhat less message-contruction in the client impl <--
- Offer aliases for frequently used impls
