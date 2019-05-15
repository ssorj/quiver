# Notes

## Debugging Rhea

    $ DEBUG=rhea:\* <command>

## Message Settlement

- Message settlement latencies are calculated using the same methods and display profiles used by message receive latencies.
- Runtime settlement latencies are calculated on a subset of the messsage stream. Runtime processing can not keep up with fast streams.
- Summary latencies are calculated using all messages in the message stream.
