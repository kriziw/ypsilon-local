[English](troubleshooting.md) | [Español](troubleshooting.es.md) | [Català](troubleshooting.ca.md)

# Connection troubleshooting

Discovery, local authentication and F79D reads are separate stages. A successful
`broadlink.hello()` does not prove that the device accepts local control.

## Setup messages and logs

Since 2.7.1, setup distinguishes a rejected local handshake (`invalid_auth`), a
rejected handshake with an advertised lock (`device_locked`), and other failures
(`cannot_connect`). The lock bit is a discovery observation, not proof of the
cause. Ypsilon still attempts the normal authentication even if that bit is true.

A failed setup emits one warning with the result, transport stage, exception
type, numeric error code, device type and advertised lock. No entry is required.
For more detail, enable debug logging from the integration's menu, or add this
to `configuration.yaml` and restart Home Assistant:

```yaml
logger:
  default: warning
  logs:
    custom_components.ypsilon_local: debug
```

Merge this into an existing `logger:` section rather than adding a second one.
Reproduce one setup attempt, collect the Ypsilon lines and disable debug again.
The new connection messages omit IP/MAC, device names, keys, packets and raw
exception messages. Review other Home Assistant logs before posting them.

For configured entries, download diagnostics from the integration/device menu.
`connection.transport` includes the last transport stage, discovered type,
advertised lock and most recent failure metadata. `last_error` retains the last
failure even after a later successful transaction; `available` indicates the
coordinator's current status. Failed initial setup has no entry to download, so
use the setup warning or standalone probe instead.

## Standalone report

In a Python environment with `python-broadlink==1.0.6` already installed, run this from
the repository root, replacing `DEVICE_IP` locally:

```bash
python scripts/debug_connection.py DEVICE_IP
```

The script attempts one discovery and one normal authentication. If authentication
succeeds, it also attempts a firmware read. It sends no configuration, lock,
provisioning or regeneration commands and does not query F79D fields. Its JSON
report contains Python/BroadLink versions, timeout and stage outcomes, but no
address, MAC, device name, control ID, keys, packet bytes or exception text. Exit
status 1 means the handshake did not succeed; a firmware-read failure is reported
separately and does not invalidate successful authentication.

Use the same Python/network environment as the original failing probe when
possible. A Terminal/SSH add-on, HA Core and a separate PC can have different
environments; say where you ran it. Do not replace HA's managed dependencies.

## If authentication is rejected

1. Report whether local authentication ever worked, the current HA/integration
   versions, app name/version, and where the probe runs.
2. Close the vendor app and pause other local clients, then run one fresh probe.
3. If the app exposes a lock/local-control setting, report its state. Check the
   vendor's guidance before changing it; its existence is not confirmed for every
   Water Device firmware.

An advertised lock plus rejection makes a local-control lock worth investigating.
A false lock bit does not prove that all local controls are allowed. App pairing
alone does not establish that a cloud-issued key is required.

BroadLink lock behaviour is documented in the [Home Assistant BroadLink guide](https://www.home-assistant.io/integrations/broadlink/#device-is-locked)
and [upstream discussion #377](https://github.com/mjg59/python-broadlink/issues/377).
Those examples concern other devices; they are not a verified G6 repair procedure.
Do not factory-reset, remove cloud pairing or send a guessed `set_lock(False)`
command as a first diagnostic step.

If rejection persists, maintainers may request a narrowly scoped discovery/auth
capture and compare it with a working G6. Agree on collection and redaction first;
do not post full PCAPs publicly because authentication captures can contain session
material and identifiers. No configuration writes are needed to investigate this.

## Reported app-pairing workaround (issue #17)

One contributor using iOS Runxin/润新 2.0.0 reported an advertised lock and rejected local authentication. Fully pairing the same unit through Water Device 2.1.3, rather than simply opening it, replaced the previous app binding and changed the advertised lock to false; standard authentication then succeeded with the app closed. No controller factory reset or physical setting change was reported. Only one of the two apps could see/control the unit afterward.

This is one documented result, not a rule for every app version or firmware. Re-pairing can replace the existing app binding; do not describe it as merely adding a second client. No cloud-issued key or automatic unlock command is implemented. There is no need to repeat this procedure or re-lock a working device for evidence.

The resulting device reports controller code 1; successful authentication does not imply G6/model-9 identity. See [issue #17](https://github.com/Danirv/runxin-local/issues/17) and [model-1 Alpha and validated manual clock](model-1-alpha.md).
