# Pet Feeder Local for Home Assistant

An experimental integration for [Pet Feeder Local Firmware](https://github.com/e2equiel/pet-feeder-local-firmware).

The integration uses the feeder's own authenticated local API. It does not require Tuya cloud credentials, a Tuya developer account, or the tuya-local integration.

## Controls

1. Select a portion count without dispensing food.
2. Press a separate **Serve** button to dispense the selected amount.
3. View and edit the feeding schedule, including weekdays, time, portions, and enabled state.
4. View the local camera stream.

Schedules belong to the feeder MCU. Home Assistant configures and displays them; it must not be required to run scheduled meals.

## Development status

The authenticated API, native camera transport, direct MCU schedule editing, and one-portion request acknowledgement have been demonstrated on one test device with Internet blocked before application startup. The original schedule was restored after testing. Physical food delivery and battery-backed operation have not been verified.

Twenty-one Python tests pass against Home Assistant 2026.11.2, covering the API client and entity behavior. DOM tests also verify that portion selection and Serve are separate, new meals start disabled, and stale revisions are preserved for conflict detection. The integration includes a config flow, portion number in box mode, Serve button, schedule sensor, MCU diagnostic sensor, calendar display, authenticated RTSP camera, and schedule editor card.

The integration has also passed live installation and end-to-end tests on HA 2026.11.2: portion selection sent no motor command; Serve sent one acknowledged request; the browser editor added and removed a disabled meal with matching MCU readback; and the local camera displayed successfully. The same local stream was decoded by Frigate 0.18.3. See [validation scope](docs/validation.md) for the remaining hardware checks.

## Installation

1. Install and validate the companion firmware overlay on a supported feeder.
2. Copy `custom_components/pet_feeder_local` into the HA configuration's `custom_components` directory. Restart Home Assistant to discover the new integration.
3. Add **Pet Feeder Local** under Settings → Devices & services. Enter `http://FEEDER_ADDRESS:8080` and the private device API token. When sharing video with Frigate, also enter the optional local go2rtc RTSP restream address.
4. Copy `frontend/pet-feeder-local-card.js` to HA's `www` directory. Add `/local/pet-feeder-local-card.js` as a JavaScript module dashboard resource.
5. Add this card, replacing entity IDs with those created for your feeder:

```yaml
type: custom:pet-feeder-local-card
schedule_entity: sensor.pet_feeder_local_scheduled_meals
portions_entity: number.pet_feeder_local_portions
serve_entity: button.pet_feeder_local_serve
```

The editor replaces the complete table of at most eight meals. It sends the revision originally loaded by the card; conflicting changes are rejected. The calendar entity displays enabled meals, while the card edits both enabled and disabled entries. There are no HA automations that execute scheduled meals.

HA synchronizes MCU wall time in HA's configured timezone every five minutes while it can reach the device. The MCU retains and executes its own table without HA, subject to valid clock and power. Backup-power retention still needs a physical test.

The camera serves HEVC. Browser playback support varies; use a local go2rtc restream/transcode where necessary. The feeder accepts one consumer per stream, so a shared go2rtc source is recommended when Frigate and HA both consume video. Audio is not available yet.

## Development

Use Python 3.14 with Home Assistant 2026.11.2 and its stream/ffmpeg dependencies to run `python -m pytest`. Run `npm install` and `npm test` for the card behavior tests. No test needs real feeding hardware or cloud credentials.

## Design requirements

- Changing the selected portion count must never dispense food.
- Feeding requests must not be blindly retried after a timeout.
- Schedule writes must validate the entire table and verify the MCU's readback.
- Concurrent changes must be detected rather than silently overwritten.
- No device credentials, private recordings, or flash dumps are committed.

All source code, comments, documentation, and commit messages use English.
