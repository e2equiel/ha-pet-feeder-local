# Pet Feeder Local for Home Assistant

An experimental integration for [Pet Feeder Local Firmware](https://github.com/e2equiel/pet-feeder-local-firmware).

The integration will use the feeder's own authenticated local API. It will not require Tuya cloud credentials, a Tuya developer account, or the tuya-local integration.

## Intended controls

1. Select a portion count without dispensing food.
2. Press a separate **Serve** button to dispense the selected amount.
3. View and edit the feeding schedule, including weekdays, time, portions, and enabled state.
4. View the local camera stream.

Schedules belong to the feeder MCU. Home Assistant configures and displays them; it must not be required to run scheduled meals.

## Development status

The camera transport has been demonstrated on one test device. The direct MCU control API and this integration are being developed and are not yet a complete, battery-validated feeding solution.

The API client has twelve passing contract tests covering one-shot feeding requests, uncertain outcomes, input validation, stale schedule revisions, verified readback, disabled meals, and redirect handling. Home Assistant entity platforms and the on-device HTTP server are not implemented yet.

## Design requirements

- Changing the selected portion count must never dispense food.
- Feeding requests must not be blindly retried after a timeout.
- Schedule writes must validate the entire table and verify the MCU's readback.
- Concurrent changes must be detected rather than silently overwritten.
- No device credentials, private recordings, or flash dumps are committed.

All source code, comments, documentation, and commit messages use English.
