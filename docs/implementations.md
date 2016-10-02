# Implementations

The `quiver-arrow` command is a wrapper that invokes an implementation
executable using standard arguments.  `quiver-arrow` tries to take
responsibility for "cooking" its inputs so implementations can focus
on mechanics.  By the same token, implementation outputs are
intentionally left raw so `quiver` and `quiver-arrow` can do the work
of presenting the results.

An implementation terminates when it has sent or received its expected
number of messages.  Each implementation invocation uses a single
connection to a single queue, meaning that a sending and a receiving
implementation together constitute a pair of communicating endpoints.

## Input

Implementations must process the following positional arguments.

    [1] output-dir      A directory for output files
    [2] mode            'client' or 'server'
    [3] operation       'send' or 'receive'
    [4] host            The socket name
    [5] port            The socket port
    [6] path            A named source or target for a message, often a queue
    [7] messages        Number of messages to transfer
    [8] bytes           Length of generated message body
    [9] credit          Size of credit window to maintain

If an implementation does not support a particular `mode`, for
instance `server`, it should raise an error at start time.

If the user doesn't supply an explicit `port`, the wrapper will pass a
hyphen (`-`) for that parameter.  The implementation must determine
what default port value to use.

Each unit of `credit` represents one message (not one byte).

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

## Exit code

Implementations must return zero on successful completion.  If there
is an error, they must return a non-zero exit code.  Some language
runtimes (notably Java) won't automatically convert uncaught
exceptions to non-zero exit codes, so you may have to do the
conversion yourself.

## Connections

Implementations must create one connection only.  They must connect
using the SASL mechanism `ANONYMOUS`.

<!-- XXX reconnect -->

## Queues, links, and sessions

Implementations must use only one queue (or similar addressable
resource), and only one link to that queue, either a sending or a
receiving link.

If the implementation API offers sessions (that is, a sequential
context for links), then the implementation must create only one
session.

## Messages

Implementations must give each message a unique ID to aid debugging.
They must also set an application property named `SendTime` containing
a `long` representing the send time in milliseconds.

By convention, message bodies are filled with as many `x`s as
indicated by the `bytes` parameter.  The `x` should be a single byte,
not a multi-byte Unicode character.

Sent messages must be non-durable and configured for
at-least-once-delivery (in JMS terms, non-persistent and
auto-acknowledge).

<!-- XXX acknowledgments -->
