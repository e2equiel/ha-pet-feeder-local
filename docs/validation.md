# Validation scope

The current implementation was tested on one privately owned V330L-DU4L-VS feeder running the supported stock 68.00.09 application with the companion overlay.

| Check | Observed result |
| --- | --- |
| Python contract and entity tests | 21 passing tests on Python 3.14 / HA 2026.11.2 |
| Frontend behavior tests | Portion selection, separate Serve, disabled defaults, stale revisions, and availability passed |
| Live HA setup | Config flow completed; all six entity platforms loaded |
| Live portion selection | Changing the selection did not increase the device's manual-command counter |
| Live Serve | A separate one-portion action increased the counter once and received MCU acknowledgement |
| Schedule action | Added a disabled fixture, verified readback, restored the original table |
| Browser editor | Unsaved changes stayed in the browser; Save updated the MCU; removing the fixture restored the original table |
| HA camera | Snapshot and live view displayed through a local go2rtc restream |
| Frigate camera | Frigate 0.18.3 decoded the same local stream and produced a snapshot |
| Device reboot | Persistent overlay, LAN API, saved MCU schedule, and authenticated RTSP returned with WAN blocked from boot |
| MCU autonomy | A scheduled-feeding serial record was captured with the complete Linux camera application stopped for 25 seconds |

The original household schedule was restored after every schedule-writing experiment. Device dumps, recordings, tokens, network addresses, and the household meal table are not published.

Physical food delivery was not observed. Battery-backed operation, MCU clock retention through complete power loss, prolonged offline operation, and additional hardware/firmware variants remain unverified. This is an experimental modification, not a production-certified feeding guarantee. The overlay retains the original proprietary application for camera encoding while its controls use the independent API and its WAN routes remain blocked.
