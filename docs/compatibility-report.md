# Collect a Runxin compatibility report in Home Assistant

Runxin Local can prepare a one-time report for a controller that is not yet supported, without installing Python, changing the model registry or enabling controls. It can also report discovery/authentication failures. Reports remain on your Home Assistant instance until you choose to share them.

## Collect and download

1. Install/update Runxin Local using HACS and restart Home Assistant.
2. Add the integration and enter the softener's local IP address. If normal setup rejects the model or connection, choose **Prepare the read-only report**. You can also enable **Prepare a read-only diagnostic report only** on the address form directly.
3. Close vendor apps and pause any other local polling client if convenient. Do not reset, unpair or change settings for this test.
4. Wait for the progress dialog, then confirm saving the diagnostic entry. The scan has an approximately three-minute network budget and bounded read attempts. Cancel stops further requests after the in-flight request finishes.
5. From that integration entry's menu in **Settings → Devices & services**, choose **Download diagnostics**. A partial or failed report is still useful; do not repeatedly rescan to obtain every field.
6. Follow the issue link in the report-ready dialog or the downloaded report. Its title/body are prepared locally; GitHub does not receive them until you open the link, and no issue or attachment is submitted automatically. Attach the downloaded JSON yourself.

The saved entry has **no entities, controls, polling or clock correction**. Restarting/reloading it or downloading diagnostics reads the saved file only; it does not contact the softener again. An existing entry at that address prevents a second diagnostic session. For an already installed normal entry, its existing **Download diagnostics** option provides the normal cached state and transport diagnostics without a new scan.

After a model is supported, delete its diagnostic entry and add the device normally. To collect a new diagnostic snapshot, delete the diagnostic entry and explicitly start another report. Deleting the entry also deletes its saved report. Diagnostic entries cannot be targeted by the configuration-write or phase-advancement services.

## Scope

- BroadLink discovery, ordinary local authentication and firmware-version read.
- Only BroadLink device type `0x520F` is queried with the observed F79D-compatible framing.
- A small identity query first. If it does not return a valid response, the diagnostic does not expand to a full field scan.
- Fields **1–52**, then smaller groups for missing fields, within time/attempt limits. Unit fields and paired volume components are queried together.
- A command guard permits only standard authentication, the library's firmware read and generated **opcode 0x09** field queries. No configuration write, clock sync, regeneration, phase advancement, lock/unlock, provisioning or reset is implemented.

These are limited local read requests, not passive observation. They create a normal authentication session and a small amount of network/device load. A successful read is evidence of a response, not proof that every field has the same meaning or that configuration writes are safe.

## Report contents and privacy

The integration's report includes software/firmware versions, advertised lock and authentication results, raw two-byte field values, per-query timestamps, omissions, numeric unmapped enums and reference interpretations. It preserves zero and false separately from missing fields. A name table from the public WaterDevice API describes known controller codes (1 F150, 9 F79D, 12 F105, 14 F136); this table does not add supported models and is not fetched from the cloud during diagnosis.

Reference meanings and units require independent confirmation on each model. Resin volume is not scaled to litres. Volume readings are decoded only with the unit and paired bytes returned together. Water usage may change between requests. Weekly-average consumption is not necessarily an app's weekly-history total, and added salt is bookkeeping rather than a measured salt level.

The integration's report excludes IP/MAC, names, serial numbers, keys, session IDs, raw packets and arbitrary exception text. It does contain controller settings, water readings and timestamps. Home Assistant also supplies its standard software/system diagnostic metadata. Redact identifiers/account details from screenshots or any other documents you attach; no tokens, passwords, cookies or packet capture are requested.

## What an issue still needs

- Brand, commercial model/capacity and visible controller reference, if known.
- A few near-simultaneous app/controller screenshots or displayed values **with units**: resin volume, hardness, flow cutoff, remaining/per-cycle capacity and regeneration schedule/durations. Share what is convenient; do not change settings for screenshots.
- For writes already performed, existing baseline/change/fresh-read/restoration evidence. The report itself never tests writes, and no new write or regeneration is needed just to request compatibility.

If Home Assistant cannot run the report, the separate [connection diagnostic](../scripts/debug_connection.py) remains available. Contact us with the displayed error and your environment; there is no need to alter Home Assistant's managed dependencies.

A periodic **model-1 Alpha** is a separate operational mode: it creates reference sensors and polls, with validated manual clock controls available from 2.9.3. Other writes require explicit test options and automatic clock correction stays blocked. See [its comparison guide](model-1-alpha.md). Downloading diagnostics from a normal entry exports cached state, including raw field pairs; it does not run the one-time collector.
