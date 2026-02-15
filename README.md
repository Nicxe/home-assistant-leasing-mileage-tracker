# Leasing Mileage Tracker
[![Buy me a Coffee](https://img.shields.io/badge/Support-Buy%20me%20a%20coffee-fdd734?logo=buy-me-a-coffee)](https://www.buymeacoffee.com/NiklasV) ![GitHub Release](https://img.shields.io/github/v/release/nicxe/home-assistant-leasing-mileage-tracker) ![GitHub Downloads (all assets, all releases)](https://img.shields.io/github/downloads/Nicxe/home-assistant-leasing-mileage-tracker/total) ![GitHub Downloads (all assets, latest release)](https://img.shields.io/github/downloads/nicxe/home-assistant-leasing-mileage-tracker/latest/total)

## Overview
A Home Assistant custom integration that tracks leased vehicle mileage against your contract terms. It calculates whether you are over or under your allowed mileage and what that means financially, so you can stay on top of your lease without surprises.

## Features

- Tracks usage from any absolute odometer sensor (km, miles, or meters)
- Compares used distance against a linear daily contract allowance
- Shows clear plus/minus balance where positive means over quota
- Calculates current and projected overage cost in SEK
- Calculates under-mile refund value in SEK with configurable cap
- Supports contract term versioning and optional early termination date
- Stores daily history internally (not dependent on Recorder)
- Emits events for threshold crossings and stale source detection
- Provides a `rebaseline` service for forward-only odometer correction


## Installation
### With HACS (Recommended)

The easiest way to install **Leasing Mileage Tracker** is via **[HACS (Home Assistant Community Store)](https://hacs.xyz/)**

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Nicxe&repository=home-assistant-leasing-mileage-tracker&category=integration)

or

1. Click on the three dots in the top right corner of the HACS overview menu.
2. Select **Custom repositories**.
3. Add the repository URL: `https://github.com/Nicxe/home-assistant-leasing-mileage-tracker`.
4. Select type: **Integration**.
5. Click the **ADD** button.

<details>
<summary>Without HACS</summary>

1. Download the latest release of the Leasing Mileage Tracker integration from **[GitHub Releases](https://github.com/Nicxe/home-assistant-leasing-mileage-tracker/releases)**.
2. Extract the downloaded files and place the `leasing_mileage_tracker` folder in your Home Assistant `custom_components` directory (usually located in the `config/custom_components` directory).
3. Restart your Home Assistant instance to load the new integration.

</details>



## Configuration
To add the Leasing Mileage Tracker integration to your Home Assistant instance, use this My button:

<p>
    <a href="https://my.home-assistant.io/redirect/config_flow_start?domain=leasing_mileage_tracker" class="my badge" target="_blank">
        <img src="https://my.home-assistant.io/badges/config_flow_start.svg">
    </a>
</p>

<details>
<summary>Manual Configuration</summary>

If the button above does not work, you can also perform the following steps manually:

1. Browse to your Home Assistant instance.
2. Go to **Settings > Devices & Services**.
3. In the bottom right corner, select the **Add Integration** button.
4. From the list, select **Leasing Mileage Tracker**.
5. Follow the on-screen instructions to complete the setup.

</details>

### Configuration parameters

- **Odometer sensor** - Any sensor with `state_class` of `total` or `total_increasing` and unit `km`, `mi`, or `m`
- **Contract start/end date** - Lease contract period
- **Contract total km** - Total allowed distance over the contract
- **Pickup odometer km** - Odometer reading at vehicle pickup
- **Overage rate** - Cost per mil (10 km) when over quota (SEK)
- **Underage refund rate** - Refund per mil when under quota (SEK)
- **Underage refund cap** - Maximum refundable distance (mil)


## Entities

### Sensors

| Entity | Description |
|--------|-------------|
| `balance_km` | Current balance in km against contract pace. Positive means over quota |
| `balance_mil` | Same balance converted to mil |
| `allowed_km_today` | Cumulative km you are allowed to have driven up to today |
| `used_km` | Cumulative km actually driven since pickup |
| `remaining_km_to_contract_end` | Remaining km to contract total. Can be negative when over |
| `daily_quota_km` | Planned quota pace per day from now |
| `weekly_quota_km` | Planned quota pace per week from now |
| `monthly_quota_km` | Planned quota pace per month from now |
| `current_overage_cost_sek` | Current overage cost based on present over-quota distance |
| `projected_overage_cost_sek` | Projected overage cost at contract end using rolling pace |
| `avoided_overage_value_sek` | Capped under-mile refund value based on current under-quota distance |

### Binary sensors

| Entity | Description |
|--------|-------------|
| `over_quota_now` | On when current balance is above quota tolerance |
| `projected_over_quota_end` | On when projection indicates overage at contract end |
| `source_stale` | On when source odometer has not updated for 48 hours |


## Service

### `leasing_mileage_tracker.rebaseline`

Applies a forward-only odometer correction and stores an audit record.

| Field | Required | Description |
|-------|----------|-------------|
| `entry_id` | Yes | Config entry ID |
| `new_odometer_km` | Yes | New odometer reading in km |
| `note` | No | Optional audit note |


## Events

The integration fires events on the Home Assistant event bus when thresholds are crossed:

- `leasing_mileage_tracker.over_quota_entered`
- `leasing_mileage_tracker.over_quota_cleared`
- `leasing_mileage_tracker.projected_overage_entered`
- `leasing_mileage_tracker.projected_overage_cleared`
- `leasing_mileage_tracker.source_stale`
- `leasing_mileage_tracker.source_recovered`


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
