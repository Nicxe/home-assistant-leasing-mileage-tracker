"""Constants for Leasing Mileage Tracker."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "leasing_mileage_tracker"

PLATFORMS: list[str] = ["sensor", "binary_sensor"]

DEFAULT_NAME = "Leasing Mileage Tracker"
DEFAULT_UNDERAGE_REFUND_RATE_SEK_PER_MIL = 5.5
DEFAULT_UNDERAGE_REFUND_MAX_MIL = 500.0

CONF_SOURCE_ENTITY_ID = "source_entity_id"
CONF_CONTRACT_START_DATE = "contract_start_date"
CONF_CONTRACT_END_DATE = "contract_end_date"
CONF_CONTRACT_TOTAL_KM = "contract_total_km"
CONF_PICKUP_ODOMETER_KM = "pickup_odometer_km"
CONF_OVERAGE_RATE_SEK_PER_MIL = "overage_rate_sek_per_mil"
CONF_UNDERAGE_REFUND_RATE_SEK_PER_MIL = "underage_refund_rate_sek_per_mil"
CONF_UNDERAGE_REFUND_MAX_MIL = "underage_refund_max_mil"
CONF_ACTUAL_END_DATE = "actual_end_date"

CONF_CONTRACT_VERSIONS = "contract_versions"
CONF_HISTORY_POINTS = "history_points"
CONF_ADJUSTMENTS = "adjustments"
CONF_LAST_VALID_ODOMETER_KM = "last_valid_odometer_km"
CONF_LAST_SOURCE_UPDATE = "last_source_update"
CONF_ANOMALY_COUNT = "anomaly_count"
CONF_LAST_ANOMALY = "last_anomaly"
CONF_EVENT_FLAGS = "event_flags"

ATTR_ENTRY_ID = "entry_id"
ATTR_ENTITY_ID = "entity_id"
ATTR_TIMESTAMP = "timestamp"
ATTR_ODOMETER_KM = "odometer_km"
ATTR_USED_KM = "used_km"
ATTR_ALLOWED_KM = "allowed_km"
ATTR_BALANCE_KM = "balance_km"
ATTR_PROJECTED_OVERAGE_KM = "projected_overage_km"
ATTR_PROJECTED_OVERAGE_COST_SEK = "projected_overage_cost_sek"
ATTR_SOURCE_STALE = "source_stale"

SERVICE_REBASELINE = "rebaseline"
ATTR_NEW_ODOMETER_KM = "new_odometer_km"
ATTR_NOTE = "note"

EVENT_OVER_QUOTA_ENTERED = f"{DOMAIN}.over_quota_entered"
EVENT_OVER_QUOTA_CLEARED = f"{DOMAIN}.over_quota_cleared"
EVENT_PROJECTED_OVERAGE_ENTERED = f"{DOMAIN}.projected_overage_entered"
EVENT_PROJECTED_OVERAGE_CLEARED = f"{DOMAIN}.projected_overage_cleared"
EVENT_SOURCE_STALE = f"{DOMAIN}.source_stale"
EVENT_SOURCE_RECOVERED = f"{DOMAIN}.source_recovered"

STORAGE_VERSION = 1
STORAGE_KEY_PREFIX = f"{DOMAIN}_"
MAX_HISTORY_POINTS = 5000
MAX_ADJUSTMENTS = 500

BALANCE_TOLERANCE_KM = 10.0
SOURCE_STALE_THRESHOLD = timedelta(hours=48)
STALE_CHECK_INTERVAL = timedelta(hours=1)

MILE_IN_KM = 1.609344
METER_IN_KM = 0.001
MIL_IN_KM = 10.0

ROLLING_WINDOW_DAYS = 30
