# Documentation

## Entity Mapping

All entities are configured in the Web UI. The backend has no fixed entity IDs.

Required smart meter entities:

- Grid import power as positive W
- Grid export power as positive W

Recommended bank entities:

- SOC in percent
- PV power in W
- AC output in W
- Setpoint entity as `number` or `input_number`

## Control Logic

House consumption is calculated as:

```text
house_consumption_w = b14_ac_output_w + b16_ac_output_w + grid_import_w - grid_export_w
```

The total output target is:

```text
target_total_w = clamp(0.70 * avg_house_w + 0.30 * short_house_w - reserve_w, 0, global_limit_w)
```

Default mode:

- B14 remains the leading bank.
- B16 supplies the remaining target where allowed.

Central mode:

- Both banks receive a weighted share based on available energy, SOC and PV.

## Failsafe Behavior

The add-on enters failsafe-style decisions when required sensor values are missing, stale or non-numeric. In dry-run mode it never writes setpoints. In manual override mode automatic writes are paused while live calculations continue.
