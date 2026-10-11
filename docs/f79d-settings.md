# F79D recovered settings semantics

This document records settings recovered from the legacy WaterDevice advanced-settings UI and keeps their Home Assistant representation explicit. It complements `f79d.md`; protocol encodability alone does not imply that a setting is safe to expose as a writable control.

## Enum fields

| Field | Protocol name | Raw values | Home Assistant states | HA policy |
|---:|---|---|---|---|
| 2 | `language` | 0 Chinese, 1 English, 2 Spanish, 3 French, 4 Russian, 5 Italian, 6 German, 7 Polish | `chinese` … `polish` | diagnostic enum, disabled by default |
| 3 | `deviceTimeScheme` | 0 12-hour, 1 24-hour | `12_hour`, `24_hour` | diagnostic enum, disabled by default |
| 24 | `outRelayMode` | 0 `b-01`, 1 `b-02` | `b_01`, `b_02` | diagnostic enum, disabled by default |
| 48 | `absorbSaltMode` | 0 reverse draw (`逆吸`), 1 forward draw (`顺吸`) | `reverse`, `forward` | diagnostic enum, disabled by default |

The stable Home Assistant state keys deliberately do not use translated text. The original raw code is retained as the `raw_code` entity attribute.

## Controller-language evidence (2.9.3)

The language row above is the **reference DeviceLanguage table**, not a universal mapping for every local controller. The [manufacturer API definition](https://api.waterdevice.net/api/abp/api-definition?includeTypes=true) types `DeviceProtocolDataDto.Language` as `Devices.Protocols.DeviceLanguage`; app/account language preferences use separate `Identity.LanguageType` / `LanguageVersion` enums. The examined frontend binds the device-language setting and account-language selector separately. Coinciding numeric codes do not prove those tables can be substituted.

Physical displays establish only these overrides:

| Controller model | Field-2 code | Reference label | Confirmed controller language |
|---|---|---|---|
| 1 (issue #17) | 7 | Polish | Dutch |
| 9 (project Ypsilon G6) | 3 | French | Spanish |

The [issue #17 reply](https://github.com/Danirv/runxin-local/issues/17#issuecomment-6096161743) confirms Dutch; the project G6 diagnostics report model 9/code 3 and its controller menus are Spanish. `device_language_keys()` applies only these pairs, with translated enum options and preserved `raw_code`. Models 12/14 and unobserved codes retain the reference labels. Missing readings remain unknown, and unknown codes remain decimal states. No language write is exposed.

The cause of the local/reference discrepancy is not demonstrated. BroadLink firmware 62016 is the Wi-Fi module firmware, not proof that two valves share the same firmware or language table.

The language sensor also reports `controller_model` and `interpretation` (`controller_display_confirmed` or `reference_device_language_enum`) so diagnostics distinguish observed labels from reference candidates.

## Numeric fields recovered from the same UI

| Field | Protocol name | WaterDevice range | HA representation |
|---:|---|---:|---|
| 13 | `washingIncreaseNumber` | 0–20 | read-only diagnostic sensor, disabled by default |
| 14 | `backWashIntervalNumber` | 0–20 | read-only diagnostic sensor, disabled by default |
| 25 | `regenerationAlarmNumber` | 5–1200 | read-only diagnostic sensor, enabled by default |

Field 25 is labelled by WaterDevice as the regeneration count used for the reminder. On the tested Ypsilon G6 the observed value is 700. It is useful as the native threshold for resin-maintenance calculations; it is **not** itself the current regeneration count.

## Existing writable settings: recovered UI limits

WaterDevice constrains field 6 (`continuousWaterTime`) to 0–120 minutes. Home Assistant mirrors this range.

Field 7 (`flowRateOff`) is unit-dependent. The integration only enables its writable `number` for the hardware-validated cubic-metre unit family (unit code 2), for which WaterDevice caps the display at 10.00 m³/h. The protocol stores hundredths, so the matching safe raw range is 0–1000.

Other currently exposed write limits remain:

- field 43 `saltAddition`: 0–100 kg;
- field 47 `rawWaterHardness`: 50–1500 mg/L.

These UI ranges are separate from write-evidence policy. On the tested Ypsilon G6, field 7 is `HARDWARE_WRITE_VERIFIED` using a 16-bit **big-endian** wire value. The decisive read-back is `03 E8` for raw 1000 / 10.00 m³/h; earlier project builds using BE also completed successful local write/read-back verification. The 2.6.x LE regression produced `593.95 m³/h` from the same bytes and failed strict write confirmation.

## Evidence source

The reference enum mappings and UI ranges above come from the recovered legacy WaterDevice JavaScript configuration and enum modules. Field-7 byte order is intentionally taken from physical G6 evidence where the recovered application interpretation conflicts with the controller. These semantics are regression-tested in `tests/test_recovered_settings_semantics.py`, `tests/test_f79d.py` and `scripts/audit.py`; translations remain complete in English, Spanish and Catalan.
