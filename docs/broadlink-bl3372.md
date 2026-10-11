[English](broadlink-bl3372.md) | [Español](broadlink-bl3372.es.md) | [Català](broadlink-bl3372.ca.md)

# BroadLink BL3372 transport

`transport/broadlink_bl3372.py` is the concrete transport used by the Home
Assistant integration today. It is intentionally separate from the F79D codec.

## Tested combination

- BroadLink device type: `0x520F`
- module family: BL3372
- product controller: Runxin F79D
- BroadLink command carrying product data: `0x6A`
- Python dependency: `python-broadlink==1.0.6`

The Home Assistant integration still probes for the tested device type/model.
The transport class is parameterised so research code can test a different
BroadLink devtype without changing the Runxin codec, but that does not make the
new combination supported by Ypsilon.

## Transaction path

```text
raw Runxin request
 -> prepend uint16-le payload length (TFB)
 -> BroadLink send_packet(0x6A, ...)
 -> validate outer BroadLink response
 -> decrypt response body
 -> remove TFB length/padding
 -> raw Runxin response
```

The transport returns the raw Runxin response. It never decodes F79D fields.

## Session handling and read retries

The transport keeps one authenticated BroadLink session and serializes
transactions. For idempotent reads:

- `-1` / `-7`: one fresh authentication/session attempt is allowed;
- `-5`: empirically transient on the tested hardware; bounded short jittered
  retries are allowed;
- the authentication budget and transient retry budget are independent.

The exact internal cause of `-5` is **not known**. The project only claims the
observed fact that it can be transient on the tested device.

## Write delivery: no blind retry

Writes use the dedicated `transact_write()` path and are sent **at most once**.
If the response is lost, the session expires, or the transport returns an outer
error after submission, delivery is ambiguous: the F79D may already have
executed the command.

The transport therefore does not retry a SET automatically. The Home Assistant
coordinator performs a new local GET and reconciles physical state. If the new
state matches the requested value, the operation is accepted despite the lost
ACK; otherwise it times out as unconfirmed. This is especially important for
mechanical actions such as forced regeneration.

A final transport/protocol failure invalidates the session so the next safe
transaction starts from a clean authentication state.

## Diagnostics

The transport exposes counters for transient read retries, re-authentication
attempts, and BroadLink firmware version when readable. These are integration
diagnostics, not protocol state.

## Replacing BroadLink

A different transport does not need to emulate BroadLink. It only needs to
accept a raw Runxin request and return a raw Runxin response. TFB, `0x6A`,
BroadLink encryption and outer errors must not leak into the generic Runxin
contract.

See [`adding-a-transport.md`](adding-a-transport.md).
