# Implementations

The `quiver-arrow` command is a wrapper that invokes an implementation
executable using standard arguments.  `quiver-arrow` tries to take
responsibility for "cooking" its inputs so implementations can focus
on mechanics.  By the same token, implementation outputs are
intentionally left raw so `quiver-arrow` can do the work of presenting
the results.

## Input

Implementations must process the following positional arguments.

    [1] output-dir      A directory for output files
    [2] mode            'client' or 'server'
    [3] operation       'send' or 'receive'
    [4] host            The socket name
    [5] port            The socket port
    [6] path            A source or target for a message, often a queue
    [7] messages        Number of messages to transfer
    [8] bytes           Length of generated message body
    [9] credit          Amount of credit to maintain

## Output

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

## Messages

Implementations must give each message a unique ID to aid debugging.
They must also set an application property named `SendTime` containing
a `long` representing the send time in milliseconds.

- Non-persistent messages
- At-least-once delivery
- Acknowledgments, please
