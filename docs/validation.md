# Validation scope

One privately owned V330L-DU4L-VS / original application 68.00.09 has been used for hardware verification. Results below distinguish the installed 0.1 prototype from the 0.2 community package. No result asserts that food physically reached the bowl.

| Check | Evidence |
| --- | --- |
| HA 2026.11.2 / Python 3.14 test suite, 0.2 | 67 passing tests; 100% line coverage in each of 13 production modules |
| Static typing, 0.2 | mypy strict passes all production modules; Ruff passes |
| Real HA lifecycle tests, 0.2 | GUI setup, duplicate/incorrect identity, discovery address changes, reauth, reconfigure, all six platforms, service registration, errors, availability, diagnostics, Repairs and unload |
| Frontend tests, 0.2 | Portion selection separate from Serve, disabled new meals, stale revisions, automatic entity links, visual editor and unavailable controls |
| Public screenshots, 0.2 | Actual installer/card/editor interfaces using synthetic disconnected demo data, captured through a browser |
| Live installation, 0.1 | Real HA setup loaded all six platforms; browser dashboard and video displayed |
| Live selection and Serve, 0.1 | Selection emitted no motor command; one explicit one-portion Serve received an MCU acknowledgement |
| Live schedule editing, 0.1 | Added and removed a disabled fixture through the HA service and browser card; exact MCU readback and original table restoration |
| Local camera, 0.1 | Main HEVC stream decoded directly and through go2rtc; HA snapshot/live view and Frigate 0.18.3 decoding passed |
| Persistent device reboot, 0.1 | Overlay, authenticated API, saved schedule and RTSP returned with WAN blocked from boot; original read-only flash hashes unchanged |
| MCU independence, 0.1 | Scheduled-feeding serial record captured with the entire Linux camera process stopped for 25 seconds; API manual-command count unchanged |

The community package keeps API v1 compatibility. Its extra lifecycle features are tested in an isolated HA instance without upgrading or restarting the user's shared live HA instance. Firmware release/installer evidence is maintained in the [companion project](https://github.com/e2equiel/pet-feeder-local-firmware/blob/main/docs/validation.md).

Physical food delivery was not observed. The test device has no batteries or microSD. Battery-backed operation, complete-power-loss clock retention, prolonged offline operation and additional hardware variants remain unverified. An electronic acknowledgement or feeding record is not proof of physical delivery. Test your own device's intended feeding and backup-power behavior before relying on it.

The original household meal table was restored after each writing experiment. Backups, credentials, household schedules and home video are private and are never published. The overlay retains proprietary camera encoding and MCU firmware; independent local controls do not make those components open source.
