# Validation scope

As of 2026-11-25, three privately owned V330L-DU4L-VS units with original application 68.00.09 have been used for hardware verification. The earlier sections describe the initial test unit (Feeder 2); the [three-device supervised results](#three-device-supervised-validation-2026-11-25) describe the later active-feeder migrations and unified dashboard. The same application/flash profile was verified on all three. Full MCU revision identification remains limited to the initial unit.

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

## Published 0.4.1 installed in live HA

The published tag was downloaded through Marketplace and loaded after one Core restart. Runtime diagnostics report 0.4.1 and the served card bytes match the published source. An all-disabled Tuesday fixture written through the actual HA action used HA mask `4`, produced raw MCU mask `16`, and read back as Tuesday in HA. The fixture was removed; the exact original table and revision were restored with no additional motor commands.

The live card shows the original three disabled rows, no redundant Days heading, full-width 56 × 44 px weekday controls and rows about 147 px tall. Camera imagery returned in HA, the browser displayed the local camera, and Frigate received about 4 fps. Other feeders’ entry metadata, 39 protected Tuya entity-registry configurations, 46 automation configurations and unrelated dashboard/restream resources were preserved. Three previously active players were still playing after the restart. Multi-feeder copy remains covered by synthetic tests only.

## Three-device supervised validation (2026-11-25)

Three physical units now have observed results. All use the same supported V330L-DU4L-VS / original application 68.00.09 application and flash profile, running overlay 0.2.0. This increases the device count, not the number of supported hardware variants. Full MCU revision identification is still limited to the initial test unit. HA integration 0.4.1 was verified on all three.

| Unit | Native installation and saved table | Physical food evidence | Isolation during the scheduled observation |
| --- | --- | --- | --- |
| Feeder 2 — test unit | Native 0.2.2 upgrade, rollback and stock-restore/first-install cycle on an already paired unit; three original disabled rows restored after experiments | Owner confirmed manual delivery, a daily meal and two single-day diagnostic meals | WAN blocked; complete Linux camera/control application paused for 25 seconds; selected HA entry also disabled in the single-day trials |
| Feeder 1 — active unit | Native 0.3.0 first installation; all eight enabled rows preserved; an explicitly authorized temporary daily test replaced one row and then restored every original field and the original revision | Owner confirmed one manual portion and the temporary scheduled meal; two camera recordings retained privately and fully decoded | Only this HA entry disabled; WAN blocked; Linux camera application continued for local video |
| Feeder 3 — active unit | Native 0.3.0 first installation; all eight enabled rows and the revision remained unchanged throughout | Owner confirmed its next original saved meal; **no manual portion, extra meal or schedule write** was requested; two camera recordings retained privately and fully decoded | Only this HA entry disabled; WAN blocked; Linux camera application continued for local video |

Each completed installation obtained two matching complete 8 MiB private backups and checked the configuration archive. First-install MCU readbacks on the active units were compared field by field with their own per-device baselines. Device identity was checked separately; equal schedules were not used as an identity check. Only the selected legacy HA entry was disabled and its history retained. The two active-unit migrations did not require an HA Core or global camera-service restart. The native installer restarted only each selected unit's Linux camera application.

Food observations combine video with the owner's direct confirmation. Pets or the housing sometimes hid the outlet, so a cat approaching the bowl was not accepted by itself as proof of dispensed food. The stronger Linux-process-pause experiment belongs to Feeder 2; it was not repeated on the active units.

Backup refusals occurred before activation on the active units. Their immutable partitions matched, but the live configuration partition changed between reads. One vendor date file updated about every five minutes; a normal retry after an observed update produced matching full backups. No comparison was bypassed, no application was paused to force a backup, and no raw flash was written. The current installer does not automate that quiet-window timing. See the firmware [recovery guide](https://github.com/e2equiel/pet-feeder-local-firmware/blob/main/docs/recovery.md).

### Unified dashboard

The live dashboard controls only Feeders 1 and 3 and displays the three feeder cameras plus an overhead view. All four 1920×1080 videos were observed playing. Both selector directions were checked. Each source offered only the other active feeder as a copy destination; destinations started unchecked, and copying stayed disabled until an explicit destination selection. **No calendar copy was executed on either active unit.** Actual copy requests, confirmation handling, revisions and partial results remain covered by disconnected synthetic tests.

The exact eight-row tables, enabled flags, revisions and manual counters on both active feeders were compared before and after configuring and checking the dashboard. They were unchanged. A 390×844 CSS-pixel mobile layout was also checked, and the temporary viewport was reset. Existing individual views remain available as subviews, and no dashboard dependency was installed for this deployment because the layout components were already present.

Existing Frigate camera names and enabled/recording settings were preserved. These results establish local HA/shared-stream playback; they do not claim that every feeder was enabled for Frigate recording. Frigate decoding has separate evidence on the initial test unit.

### Limits and public evidence

The active units use UPS-backed mains power and have no batteries. Battery operation, complete-power-loss clock retention, measured UPS runtime, prolonged offline reliability, every individual weekday and other device variants remain untested. Factory-fresh/unpaired onboarding has not been tested; one-time Tuya/Smart Life Wi-Fi pairing is still the validated starting point. Audio and the separate video substream are not supported by the normal setup.

The [machine-readable summary](validation-2026-11-25.json) contains only allowlisted results. Raw backups, tokens, addresses, device IDs, household meal times and home recordings remain private. Public dashboard screenshots use the actual bundled controls in a disconnected preview with synthetic schedules and illustrated camera placeholders; they are not screenshots of a real meal or home-camera feed. See the [unified dashboard setup and previews](unified-dashboard.md).
