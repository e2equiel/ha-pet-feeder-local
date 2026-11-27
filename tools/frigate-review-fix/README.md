# Frigate 0.18.3 manual-review recording fix

This optional compatibility image addresses a Frigate 0.18.3 recording issue. When a finite manual event arrives during an existing detection review, Frigate changes the review's severity in memory without immediately publishing it. Recording retention can still see a detection instead of an alert and discard quiet footage. A later review update does not recover segments already discarded.

The patch immediately publishes manual changes to an existing review. It keeps the original finite event duration and recording policy. It does not change feeding schedules, detection models, camera configuration, or normal motion retention.

The Dockerfile extends a pinned official 0.18.3 image. The script accepts only the exact upstream source hash, verifies the patched result, and refuses other versions. Do not carry this patch over to another Frigate version without reviewing the upstream code.

## Build and use

Run on the computer that runs Frigate, from this repository:

```sh
docker build --pull=false -t frigate:0.18.3-pet-feeder-review-fix tools/frigate-review-fix
```

Back up your Compose file. Change only the Frigate service's `image` to `frigate:0.18.3-pet-feeder-review-fix`, retaining its volumes, devices, ports and other settings. Recreate only that service:

```sh
docker compose up -d --no-deps --pull never frigate
```

This briefly interrupts Frigate recordings. Home Assistant and the feeder MCU schedules are independent of this restart.

Verify the review becomes an alert immediately when a manual capture window starts during an existing detection. Verify the complete requested recording interval, including quiet footage, before relying on a collage. An accepted event or successful HTTP response alone does not establish that footage was retained.

## Roll back

Restore the original `image` value from your Compose backup and recreate only Frigate using the same command. Configuration, recordings and the original official image are retained. Rebuild the compatibility image from this Dockerfile when moving this installation to another host.
