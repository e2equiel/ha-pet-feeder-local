# Changelog

## 0.5.0

- Emit deduplicated scheduled-feeding events from passive MCU telemetry in overlay 0.2.1. Persist the event cursor and ignore stale reports; manual ACKs and calendar predictions are not feeding events.
- Add optional durable Frigate/Telegram video notifications: silent 25x custom exports, exact export IDs, simultaneous-feeder merging, ownership-checked cleanup and restart recovery. Uncertain Telegram sends are not blindly repeated.
- Preserve existing meal tables, manual-feeding controls and compatibility with older overlays. Video notifications use the already configured Frigate and Telegram services.

## 0.4.1

- Use the installed integration version for the automatically registered frontend URL so browser caches load the current compact card after updates. Entity setup, schedules and firmware are unchanged.

## 0.4.0

- Correct the seven-bit weekday conversion between HA (Sunday bit 0) and the supported MCU/raw API (Saturday bit 0). Physical single-day trials exposed the mismatch hidden by daily and Monday–Friday masks. Existing schedules are not rewritten during upgrade; review weekday-specific rows.
- Compact meal rows, remove the redundant Days heading, and let weekday controls fill the available width with 44 px touch targets. Eight desktop rows use about 40% less height.
- Add a multi-feeder selector with independent unsaved drafts. Copy the displayed schedule to explicitly selected feeders after confirmation, with individual revision checks and per-device results. Serve always targets the selected feeder only.
- Add asymmetric weekday and all-mask protocol regressions plus synthetic multi-feeder interaction tests. Document physically observed manual and autonomous meals, separately from remaining battery and power-loss checks.

## 0.3.0

- Redesign the dashboard card and visual editor around the original integration icon, neutral HA theme surfaces, clear sections and responsive controls.
- Distinguish enabled meals from saved rows and show unsaved edits. Keep weekday selections visible with checkbox semantics and at least 44 px touch targets.
- Require a valid portion selection before Serve, preserve incomplete time drafts when adding/removing rows, and confirm before discarding unsaved schedule changes.
- Preserve service payloads, entity identities, revision protection and disabled-by-default new meals. No firmware, camera or scheduling protocol changes.

## 0.2.1

- Add an original integration icon featuring the local feeder inside a home. The native Mac installer uses a complementary installer icon.
- Keep all entities, controls, schedules, camera behavior and configuration unchanged.

## 0.2.0

Community release with bundled dashboard controls, MCU meal editing, local video, discovery, reauthentication, diagnostics and lifecycle support.
