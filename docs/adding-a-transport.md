[English](adding-a-transport.md) | [Español](adding-a-transport.es.md) | [Català](adding-a-transport.ca.md)

# Adding another transport

The reusable F79D client consumes a deliberately small structural interface:

```python
class MyTransport:
    def transact(self, frame: bytes) -> bytes:
        """Send one raw Runxin frame and return one raw Runxin frame."""
        ...
```

Optional hooks are recognised when present:

```python
class MyTransport:
    def transact(self, frame: bytes) -> bytes: ...
    def transact_write(self, frame: bytes) -> bytes: ...  # optional, non-idempotent path
    def invalidate(self) -> None: ...                      # reset session/framing
    def close(self) -> None: ...                           # release resources
```

The client can then be used without Home Assistant:

```python
from runxin.client import F79DClient

client = F79DClient(MyTransport(...))
identity = client.read_identity()
state = client.read_state()
```

`F79DClient` is a wire-level tool: it does not enforce the integration’s model permissions. The HA composition adapter adds those guards. A standalone caller must establish model/range compatibility and physical read-back before using writes; the example above only reads.

When experimenting outside this repository, vendor/copy the pure `runxin/`
package or use it from a source checkout. Do not create a Home Assistant custom
integration that imports another installed custom integration at runtime.

## Read versus write delivery semantics

`transact()` is the ordinary transaction path and may use bounded retries when
the request is known to be idempotent, such as a state query.

`transact_write()` is optional. Implement it when the transport cannot prove
that a failed response means the controller did not execute the command. A
write transport must **not blindly resend** a command after a timeout, broken
session, or lost acknowledgement: the physical controller may already have
applied it. The caller should reconcile through an independent read-back first.

If a transport does not implement `transact_write()`, `F79DClient` falls back to
`transact()` for compatibility. New stateful transports should normally provide
the dedicated write hook.

## What transactions must return

Return the **raw Runxin frame**, starting with `5A 5C`. Do not return:

- a BroadLink encrypted packet;
- the BL3372 TFB length prefix;
- serial/TCP framing bytes belonging only to your adapter;
- already decoded dictionaries.

Your transport is responsible for removing its own envelope before handing the
response to `F79DClient`.

## Examples of future transports

Potential transports include direct UART/serial, TCP bridges, ESPHome-backed
links or another vendor Wi-Fi module. None are supported until tested.

A new transport should live under `transport/` and should ideally subclass
`RunxinTransport` from `transport/base.py`. The F79D client uses structural
typing, so subclassing is convenient but not mandatory.

## Tests required for a contribution

Add offline tests that prove at least:

1. the transport sends the exact raw Runxin request unchanged;
2. its envelope is added/removed only in the transport layer;
3. malformed/truncated responses fail closed;
4. read retry/session reset behavior is bounded;
5. writes are not blindly duplicated after ambiguous delivery;
6. `runxin/` remains free of transport-specific imports.

Real-hardware validation must be documented separately from simulated tests.
Do not enable automatic discovery for a new hardware family until its identity
and false-positive behavior are understood.
