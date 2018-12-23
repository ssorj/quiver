# Quiver implementations

Quiver contains two components that have switchable underlying
implementations, arrows and servers.  An arrow usually plays the role
of a client, though it can be used in peer-to-peer mode as well.  A
server is a message broker or router.

## Arrow implementations

The `quiver-arrow` command is a wrapper that invokes an implementation
executable using standard arguments.  `quiver-arrow` tries to take
responsibility for "cooking" its inputs so implementations can focus
on mechanics.  By the same token, implementation outputs are
intentionally left raw so `quiver` and `quiver-arrow` can do the work
of presenting the results.

An arrow implementation terminates when it has sent or received its
expected number of messages.  Each invocation uses a single connection
to a single queue, meaning that a sending and a receiving
implementation together constitute a pair of communicating endpoints.

### Files

Implementations live under `impls/` in the source tree, with a name
starting with `quiver-arrow-`.  Any build or install logic should be
placed in the project `Makefile`.

The details of new implementations should be added by adding an
`_Impl` instance to `python/quiver/common.py.in`.

### Input

Implementations must process the following positional arguments.

     [1] connection-mode   'client' or 'server'
     [2] channel-mode      'active' or 'passive'
     [3] operation         'send' or 'receive'
     [4] id                A unique identifier for the application
     [5] host              The socket name
     [6] port              The socket port (or '-')
     [7] path              A named source or target for a message, often a queue
     [8] duration          
     [9] count             Number of messages to transfer
    [10] body-size         Length of generated message body
    [11] credit-window     Size of credit window to maintain
    [12] transaction-size  Size of transaction batches; 0 for no transactions
    [13] flags             Comma-separated list of named tokens

If an implementation does not support a particular `connection-mode`
or `channel-mode`, for instance `server`, it should raise an error at
start time.

Each unit of `credit-window` represents one message (not one byte).

### Output

Implementations must print sent transfers to standard output, one
transfer per line.

    <message-id>,<send-time>\n

Implementations must print received transfers to standard output, one
transfer per line.

    <message-id>,<send-time>,<receive-time>\n

Time values are unix epoch milliseconds.

    10,1472344673324,1472344673345

To avoid any performance impact, take care that writes to standard
output are buffered.  Make sure any buffered writes are flushed before
the implementation exits.

### Exit code

Implementations must return zero on successful completion.  If there
is an error, they must return a non-zero exit code.  Some language
runtimes (notably Java) won't automatically convert uncaught
exceptions to non-zero exit codes, so you may have to do the
conversion yourself.

### Connections

Implementations must create one connection only.  They must connect
using the SASL mechanism `ANONYMOUS`.

When `connection-mode` is `client`, the implementation must establish
an outgoing connection.  When it is `server`, the imlementation must
listen for an incoming connection.

<!-- XXX reconnect -->

### Queues, links, and sessions

Implementations must use only one queue (or similar addressable
resource), and only one link to that queue, either a sending or a
receiving link.

If the implementation API offers sessions (that is, a sequential
context for links), then the implementation must create only one
session.

When `channel-mode` is `active`, the implementation must initiate
creation of the sessions and links.  When it is `passive`, the
implementation must instead wait for initiation from the peer and then
confirm their creation.

### Messages

Implementations must give each message a unique string ID to aid debugging.
They must also set an application property named `SendTime` containing
a `long` representing the send time in milliseconds.

By convention, message bodies are filled with as many `x`s as
indicated by the `body-size` parameter.  The `x` must be a single
byte, not a multi-byte Unicode character.

<!--
XXX message format

The document should state:
- order and meaning of argv parameters
- message format:
  - durable - set from parameters
  - message-id - allowed types (just string?), max size
  - body - allowed types, size from parameters
  - application-properties - map layout, key name and data type
  - any others?

XXX

Sent messages must be non-durable and configured for
at-least-once-delivery (in JMS terms, non-persistent and
auto-acknowledge).
-->

<!-- XXX acknowledgments -->

<!--
## Server implementations

*XXX*
-->
