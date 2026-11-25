# Validation scope

One privately owned V330L-DU4L-VS / original application 68.00.09 has been used for hardware verification. Results below distinguish the 0.1 prototype, isolated tests of 0.2, and the published 0.2.1 package installed in live HA. Later physical observations are recorded separately below.

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
| Live Marketplace upgrade, 0.2.1 | Published tag installed over the initial prototype through Marketplace; one approved HA Core restart; running diagnostics report integration version 0.2.1 |
| Live reconfiguration, 0.2.1 | Reconfigure rejected an invalid token while the existing entry stayed loaded, then accepted the installer-generated fresh token with `reconfigure_successful`; existing entry and optional restream setting preserved |
| Preserved device state, 0.2.1 | Exact three-row MCU table and durable journal unchanged; MCU connected, clock synchronized and manual-command count zero; no feeding or schedule-write action issued for this upgrade |
| Bundled frontend and camera, 0.2.1 | Served card bytes match the published source; only this project's legacy resource URL updated. HA camera remained available and Frigate decoded the newly authenticated stream at about 4 fps without a Frigate restart |
| Other devices, 0.2.1 | Feeders 1 and 3 entry metadata unchanged; protected configuration fields and 39 Tuya entity-registry records unchanged; unrelated dashboard resources and restream configuration preserved |

The community package keeps API v1 compatibility. Automated lifecycle coverage runs in an isolated HA instance; the published 0.2.1 upgrade and reconfiguration were also exercised on the same real test unit as described above. The configuration flow's negative-token test made read-only authentication requests; the successful update reloaded only the selected entry after the one Core restart needed to load the new integration code. Firmware release/installer evidence is maintained in the [companion project](https://github.com/e2equiel/pet-feeder-local-firmware/blob/main/docs/validation.md).

Earlier prototype receipts did not establish physical delivery; the observations below do. The test device has no batteries or microSD. Battery-backed operation, complete-power-loss clock retention, prolonged offline operation and additional hardware variants remain unverified. An electronic acknowledgement or feeding record is not proof of physical delivery. Test your own device's intended feeding and backup-power behavior before relying on it.

The original household meal table was restored after each writing experiment. Backups, credentials, household schedules and home video are private and are never published. The overlay retains proprietary camera encoding and MCU firmware; independent local controls do not make those components open source.

## 0.4 software validation

70 passing Python tests with 100% line coverage in each of 13 production modules; all 128 weekday masks round-trip, asymmetric weekday read/write and invalid-mask regressions pass. Strict mypy, Ruff, coverage thresholds and frontend interaction tests pass. Frontend fixtures cover selector targeting, separate drafts, preflight, explicit confirmation, partial copy results and no automatic retry.

## 0.4 physical autonomy and weekday correction

The owner confirmed food arrived for one manual one-portion Serve, one daily scheduled meal, and two single-day diagnostic meals on the same test unit. During each successful scheduled window, Internet routing was blocked, the entire Linux camera/control application was paused for 25 seconds, and its local API was unreachable. The MCU emitted a scheduled row record and the API manual-command count stayed unchanged. No HA feeding automation issued the meal. The selected HA entry was also disabled for the single-day clock-isolation trials.

An initial Tuesday-only raw mask `4` did not feed, while daily `127` did. A comparison on actual Tuesday delivered only raw mask `16`. With the MCU date temporarily advanced to Wednesday, raw mask `8` also delivered. This supports reversing the seven weekday bits at the client/API boundary. Tuesday and Wednesday have direct hardware evidence; other individual days follow that inferred model and all 128 masks have software round-trip tests. Changing the year encoding alone did not resolve the failed Tuesday trial and is not included as a fix.

Every trial restored the original disabled table and revision; the real clock and selected HA entry were restored afterward. Other feeders were not accessed or actuated. These short tests establish actual scheduled food delivery independent of the running Linux control application and its HA/Internet connection. They do not establish battery operation, clock retention through total power loss, prolonged offline reliability, every weekday, or additional hardware variants.

The compact card and multi-device copy are tested against synthetic devices; no household feeder was used as a copy destination. Public screenshots use synthetic meals and names.
