# Scheduled feeding notifications

Integration 0.5.0 with overlay 0.2.1 exposes `pet_feeder_local_scheduled_feeding` on Home Assistant's event bus. Its source is the MCU's observed `FF FC 07 05` scheduled-row record, not a time trigger, a calendar prediction or the manual command counter. The MCU continues to own and execute its schedule when HA or the network is unavailable.

The event includes `config_entry_id`, `device_id`, `feeder_name`, a unique `event_id`, timezone-aware `occurred_at`, `source: mcu_scheduled_row`, and `meal` with HA weekday bits. `physical_delivery_confirmed: false` is intentional: a controller report does not prove that a nonempty hopper delivered food. Use video or direct observation for that claim.

The event cursor is saved before emission. Duplicate polls and HA reconnects do not replay a meal. First connection establishes a baseline, and reports older than two minutes are not emitted. A process restart creates a new random identity. A manual motor acknowledgement is never a scheduled-feeding event. Older overlays remain usable for the existing controls but cannot provide this telemetry.

## Frigate and Telegram

The optional `pet_feeder_local.queue_feeding_video` action receives the event timestamp and ID. It saves a bounded queue before returning, combines reports from feeders within 45 seconds when they share a camera and Telegram destination, and captures from 15 seconds before to 225 seconds after the execution report by default. After a 20-second recording-settle margin, it requests an explicit Frigate 0.18 custom export with `setpts=0.04*PTS` and `-an`.

The worker follows the returned export ID and waits for completion. Telegram fetches that exact file into memory through HA; there is no second persistent local video copy. After Telegram returns a chat/message response, the export and thumbnail are deleted through Frigate's ID-based API. The recording retention policy is unchanged.

Failures produce a persistent HA notification. Cleanup is retained in the queue when Frigate is unavailable, and resumes after HA restarts. If HA stops during a Telegram send, its outcome is uncertain: the worker cleans up instead of blindly sending it again. The action does not inspect a folder's latest filename, depend on a folder-size sensor, retry a feeding command, or change any schedule.

The export catalog and the NVR job queue are checked separately: an export can be queued or running before its file appears in the catalog. A temporary catalog 404 does not discard ownership of a job that can finish later. Encoding is capped at a 3.5 Mbit/s maximum video rate to keep the supported clip durations comfortably below Telegram's upload limit.

Use the internal Frigate origin reachable by HA (for example, `http://frigate.local:5000`). This first implementation uses Frigate's trusted internal API; do not expose that API publicly. Preserve the Telegram config entry already used for your own feeding videos. Optional video notifications require those two existing integrations; normal feeder control does not.

```yaml
triggers:
  - trigger: event
    event_type: pet_feeder_local_scheduled_feeding
conditions:
  - condition: template
    value_template: >-
      {{ trigger.event.data.config_entry_id in ['FEEDER_1_ENTRY', 'FEEDER_3_ENTRY'] }}
actions:
  - action: pet_feeder_local.queue_feeding_video
    data:
      event_id: "{{ trigger.event.data.event_id }}"
      occurred_at: "{{ trigger.event.data.occurred_at }}"
      feeder_name: "{{ trigger.event.data.feeder_name }}"
      frigate_url: http://frigate.local:5000
      camera: feeding_station_overhead
      telegram_config_entry_id: YOUR_TELEGRAM_ENTRY
mode: queued
max: 16
```

Disable an older time/folder-triggered sender before testing exports so both paths cannot send the same video. Remove only exports whose ownership is established; do not empty a shared directory or remove unrelated manual exports.
