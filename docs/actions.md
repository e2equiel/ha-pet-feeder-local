# Actions and examples

## Two-step manual serving

For an intentional manual command, set the selected number, then press the separate button. Replace example entity IDs with your own. Merely running the first action never serves food. If the second action reports an unknown outcome, inspect the feeder; do not automatically retry it.

```yaml
sequence:
  - action: number.set_value
    target:
      entity_id: number.pet_feeder_local_portions
    data:
      value: 2
  - action: button.press
    target:
      entity_id: button.pet_feeder_local_serve
```

## MCU schedule action

The visual card reads the scheduled meals sensor, keeps its revision while you edit, and sends one `pet_feeder_local.set_schedule` action. For scripts, use the same fields:

```yaml
action: pet_feeder_local.set_schedule
data:
  config_entry_id: YOUR_INTEGRATION_ENTRY_ID
  expected_revision: "COPY_THE_SENSOR_REVISION"
  meals:
    - weekdays: 62
      hour: 8
      minute: 30
      portions: 2
      enabled: false
```

`62` selects Monday–Friday (Sunday bit 0); `127` selects every day. The example starts disabled. The action replaces the entire table, including disabled rows, and allows at most eight entries. Keep any existing rows you want to retain. A changed revision is rejected, and a mismatch between requested meals and the MCU readback is reported as an error. Never substitute a stale hard-coded revision in a recurring automation.

## Use cases

- Adjust a weekly meal directly on the feeder, then leave HA off without moving the timer into HA.
- Serve an additional meal deliberately with two separate controls.
- Display upcoming enabled meals in HA's standard calendar card.
- Record the local camera in Frigate using a shared go2rtc connection.
- Alert on availability or the optional MCU connectivity diagnostic using standard HA state triggers and conditions.

No integration-specific triggers or conditions are registered. Camera use does not require a Tuya stream acquisition service.
