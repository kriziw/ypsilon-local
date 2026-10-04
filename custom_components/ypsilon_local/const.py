"""Home Assistant/Ypsilon integration policy constants."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "ypsilon_local"

CONF_SCAN_INTERVAL: Final = "scan_interval"
DEFAULT_SCAN_INTERVAL: Final = 60
MIN_SCAN_INTERVAL: Final = 15
MAX_SCAN_INTERVAL: Final = 3600
UPDATE_INTERVAL: Final = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

# Accepted controller models (F79D field 1) and their names live in models.py.
EXPECTED_DEVTYPE: Final = 0x520F
# Fallbacks before the first state read.
MODEL_NAME: Final = "Ypsilon G6"
MANUFACTURER: Final = "ATH / BWT / Runxin"

FIELD52_REFRESH: Final = 3600
FIELD52_FAIL_BACKOFF: Final = 300
MAX_TOLERATED_FAILURES: Final = 3

CONF_ACTIVE_SCAN_INTERVAL: Final = "active_scan_interval"
DEFAULT_ACTIVE_SCAN_INTERVAL: Final = 10
MIN_ACTIVE_SCAN_INTERVAL: Final = 5
CONF_ADAPTIVE_POLLING: Final = "adaptive_polling"
DEFAULT_ADAPTIVE_POLLING: Final = True
ACTIVE_LINGER_SECONDS: Final = 60

WRITE_SETTLE_DELAY: Final = 0.5
WRITE_VERIFY_TIMEOUT: Final = 5.0
WRITE_VERIFY_INTERVAL: Final = 0.5
MECHANICAL_VERIFY_TIMEOUT: Final = 15.0
MECHANICAL_VERIFY_INTERVAL: Final = 1.0

FLOW_RATE_SCALE_BY_UNIT: Final = {
    0: 0.01,
    1: 0.01,
    2: 0.01,
}
FLOW_RATE_SCALE_DEFAULT: Final = 0.01

FIELD_CURRENT_TIME: Final = 4
FIELD_WASH_INITIATION_TIME: Final = 5
FIELD_CONTINUOUS_WATER_TIME: Final = 6
FIELD_FLOW_RATE_OFF: Final = 7
FIELD_REGENERATING_TRIGGER_TIME: Final = 10
FIELD_SYSTEM_MODE: Final = 34
FIELD_SALT_ADDITION: Final = 43
FIELD_RAW_WATER_HARDNESS: Final = 47
FIELD_HOLIDAY_MODE: Final = 49

SERVICE_WRITE_FIELDS: Final = "write_fields"
SERVICE_ADVANCE_PHASE: Final = "advance_phase"

# The generic admin service is intentionally limited to reversible settings.
# Mechanical/state-machine fields 34 and 49 must use their purpose-specific
# controls so semantic preconditions cannot be bypassed.
WRITABLE_FIELDS: Final = frozenset(
    {
        FIELD_CURRENT_TIME,
        FIELD_REGENERATING_TRIGGER_TIME,
        FIELD_SALT_ADDITION,
        FIELD_RAW_WATER_HARDNESS,
        FIELD_CONTINUOUS_WATER_TIME,
        FIELD_FLOW_RATE_OFF,
    }
)

# Ranges mirror the recovered WaterDevice settings UI for the supported F79D.
# Field 7 is raw hundredths; the HA control is enabled only in unit code 2,
# where WaterDevice caps the displayed value at 10.00 m³/h => raw 1000.
SAFE_RAW_WRITE_RANGES: Final = {
    FIELD_CONTINUOUS_WATER_TIME: (0, 120),
    FIELD_FLOW_RATE_OFF: (0, 1000),
    FIELD_SALT_ADDITION: (0, 100),
    FIELD_RAW_WATER_HARDNESS: (50, 1500),
}

CONF_AUTO_SYNC_CLOCK: Final = "auto_sync_clock"
DEFAULT_AUTO_SYNC_CLOCK: Final = True
CONF_CLOCK_TOLERANCE: Final = "clock_tolerance_minutes"
DEFAULT_CLOCK_TOLERANCE: Final = 2
MIN_CLOCK_TOLERANCE: Final = 1
MAX_CLOCK_TOLERANCE: Final = 60
CLOCK_SYNC_RETRY_SECONDS: Final = 900

ALERT_FIELDS: Final = (
    ("saltShortageAlarm", "low_brine_concentration"),
    ("saltShortageReminder", "salt_shortage_reminder"),
    ("resinReplacementReminder", "resin_replacement"),
    ("filterMaterialReminder", "filter_reminder"),
)
