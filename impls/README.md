# Quiver implementations

Quiver contains two components that have switchable underlying
implementations, arrows and servers.  An arrow usually plays the role
of a client, though it can be used in peer-to-peer mode as well.  A
server is a message broker or router.

## Files

Implementations live under `impls/` in the source tree, with a name
starting with `quiver-arrow-` or `quiver-server-`.  Any build or
install logic should be placed in the project `Makefile`.

The details of new implementations should be added by adding an
`_Impl` instance to `python/quiver/common.py.in`.

## Arrow implementations

The `quiver-arrow` command is a wrapper that invokes an implementation
executable using standard arguments.  `quiver-arrow` takes
responsibility for "cooking" its inputs so implementations can focus
on mechanics.  By the same token, implementation outputs are
intentionally left raw so `quiver` and `quiver-arrow` can do the work
of presenting the results.

An arrow implementation terminates when it has run longer than the
requested duration or it has sent or received the expected number of
messages.  Each invocation uses a single connection to a single queue,
meaning that a sending and a receiving implementation together
constitute a pair of communicating endpoints.

### Input

The implementations take named arguments, with key and value separated
by `=`.  They must process the following arguments.

    connection-mode   string   'client' or 'server'
    channel-mode      string   'active' or 'passive'
    operation         string   'send' or 'receive'
    id                string   A unique identifier for the application
    host              string   The socket name
    port              string   The socket port (or '-')
    path              string   A named source or target for a message, often a queue
    duration          integer  Run time in seconds; 0 means no limit
    count             integer  Number of messages to transfer; 0 means no limit
    body-size         integer  Length of generated message body
    credit-window     integer  Size of credit window to maintain
    transaction-size  integer  Size of transaction batches; 0 means no transactions
    durable           integer  1 if messages are durable; 0 if non-durable
    settlement        integer  1 if message settlement latency is tracked; 0 if not tracked

If an implementation does not support a particular option, for
instance connection mode `server`, it should raise an error at start
time.

Each unit of `credit-window` represents one message (not one byte).

The follow arguments are options.

    scheme            string   protocol scheme
    username          string   username used to connect to the peer
    password          string   password used to connect to the peer
    cert              string   certificate file that identifies the arrow to the peer 
    key               string   private key file associated with the certificate

Implementations should avoid validating inputs.  That's the job of the
wrapper.  The wrapper and the implementation are closely coupled by
design.

### Output

Implementations must print sent transfers to standard output, one
transfer per line.

    <message-id>,<send-time>\n

Implementations must print received transfers to standard output, one
transfer per line.

    <message-id>,<send-time>,<receive-time>\n

Sender implementations that support settlement tracking must print message settlement
times to standard out, one settlement per line. Settlement lines are interleaved with
with sender sent transfer records. Settlement times and are identified by a prefix letter
'S' or by a prefix letter 's'. Settlement lines beginning with 'S' are included in the
run time average settlement latency calculations while lines beginning with 's' are not.
All settlement latency records are included in the summary latency computations and 
reports.

    S<message-id>,<settlement-time>\n
    s<message-id>,<settlement-time>\n

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

Implementations must give each message a unique ID to aid debugging.
They must also set an application property named `SendTime` containing
a `long` representing the send time in milliseconds.

By convention, message bodies are filled with as many `x`s as
indicated by the `body-size` parameter.  The `x` must be a single
byte, not a multi-byte Unicode character.

### Message Settlement

Message settlement tracking requires that a client library provides
access to settlement disposition tags. Not all libraries have an
this capability.

Implementations that support message settlement tracking must print
settlement records for the first message and for every 256th message
thereafter prefixed with 'S'. Other settlement records are prefixed
with 's'.

The following clients support message settlement tracking:

- qpid-proton-c
- qpid-proton-python
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

### Input

The implementations take named arguments, with key and value separated
by `=`.  They must process the following arguments.

    host        string  The listening socket name
    port        string  The listening socket port
    path        string  A named source or target for a message, often a queue
    ready-file  string  A file used to indicate the server is ready

-->
