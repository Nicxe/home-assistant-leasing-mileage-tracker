# Leasing Mileage Tracker

Leasing Mileage Tracker is a Home Assistant custom integration that tracks leased vehicle mileage against your contract terms.

## Features

- Tracks usage from an absolute odometer sensor
- Compares used distance against a linear daily contract allowance
- Shows clear plus/minus balance where positive means over quota
- Calculates current and projected overage cost in SEK
- Calculates under-mile refund value in SEK with configurable cap (mil)
- Supports contract term versioning and optional early termination date
- Lets you replace the odometer sensor from the integration options
- Stores daily history internally (not dependent on Recorder)
- Emits events for threshold crossings and stale source detection
- Provides a `rebaseline` service for forward-only correction

## Setup

1. Copy `leasing_mileage_tracker` to `/config/custom_components/`
2. Restart Home Assistant
3. Add integration: **Leasing Mileage Tracker**
4. Configure:
   - Odometer sensor
   - Contract start/end date
   - Contract total km
   - Pickup odometer km
   - Overage rate (SEK per mil)
   - Underage refund rate (SEK per mil)
   - Underage refund cap (mil)

## Source Sensor Requirements

The selected odometer sensor must:

- Be in `sensor` domain
- Have a numeric state
- Use unit `km`, `mi`, or `m`
- Have `state_class` of `total` or `total_increasing`

The odometer sensor can be changed later from the integration's **Configure**
dialog. Existing contract settings, history, and entities are preserved, and the
new sensor is used after the integration reloads.

## Entities

### Sensors

- `contract_start_date`: Configured contract start date
- `contract_end_date`: Configured contract end date
- `balance_km`: Current balance in km against contract pace. Positive means over quota
- `balance_mil`: Same balance as above, converted to mil
- `allowed_km_today`: Cumulative km you are allowed to have driven up to today
- `used_km`: Cumulative km actually driven since pickup
- `remaining_km_to_contract_end`: Remaining km to contract total. Can be negative when over total
- `daily_quota_km`: Planned quota pace per day from now
- `weekly_quota_km`: Planned quota pace per week from now
- `monthly_quota_km`: Planned quota pace per month from now
- `current_overage_cost_sek`: Current overage cost based on present over-quota distance
- `projected_overage_cost_sek`: Projected overage cost at contract end using rolling pace
- `avoided_overage_value_sek`: Capped under-mile refund value based on current under-quota distance

### Binary sensors

- `over_quota_now`: `on` when current balance is above quota tolerance
- `projected_over_quota_end`: `on` when projection indicates overage at contract end
- `source_stale`: `on` when source odometer has not updated for 48 hours

## Service

### `leasing_mileage_tracker.rebaseline`

Applies a forward-only odometer correction and stores an audit record.

Fields:

- `entry_id` (required)
- `new_odometer_km` (required)
- `note` (optional)

## Events

- `leasing_mileage_tracker.over_quota_entered`
- `leasing_mileage_tracker.over_quota_cleared`
- `leasing_mileage_tracker.projected_overage_entered`
- `leasing_mileage_tracker.projected_overage_cleared`
- `leasing_mileage_tracker.source_stale`
- `leasing_mileage_tracker.source_recovered`

Event payload includes:

- `entry_id`
- `entity_id`
- `timestamp`
- `odometer_km`
- `used_km`
- `allowed_km`
- `balance_km`
- `projected_overage_km`
- `projected_overage_cost_sek`
- `source_stale`

## Lovelace Examples

### Core status entities

```yaml
type: entities
title: Leasing status
entities:
  - entity: sensor.my_car_balance_km
  - entity: sensor.my_car_balance_mil
  - entity: sensor.my_car_allowed_km_today
  - entity: sensor.my_car_used_km
  - entity: binary_sensor.my_car_over_quota_now
  - entity: binary_sensor.my_car_projected_over_quota_end
```

### Cost and refund overview

```yaml
type: entities
title: Cost and refund
entities:
  - entity: sensor.my_car_current_overage_cost_sek
  - entity: sensor.my_car_projected_overage_cost_sek
  - entity: sensor.my_car_avoided_overage_value_sek
```

### Conditional warning

```yaml
type: conditional
conditions:
  - condition: state
    entity: binary_sensor.my_car_over_quota_now
    state: "on"
card:
  type: markdown
  content: |
    **Warning:** Current usage is above allowed contract pace.
```
