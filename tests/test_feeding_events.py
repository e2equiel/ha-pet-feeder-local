"""MCU telemetry is not a clock trigger or a manual-feed acknowledgement."""

import copy
from unittest.mock import AsyncMock

import pytest

from custom_components.pet_feeder_local.feeding_events import EVENT_SCHEDULED_FEEDING, ScheduledFeedingEvents

BOOT = "0123456789abcdef0123456789abcdef"


def envelope(sequence=0, age=1500):
    return {
        "boot_id": BOOT,
        "sequence": sequence,
        "events": []
        if not sequence
        else [
            {
                "sequence": sequence,
                "age_ms": age,
                "meal": {"weekdays": 16, "hour": 18, "minute": 15, "portions": 2, "enabled": True},
            }
        ],
    }


async def tracker(hass, cursor=None):
    t = ScheduledFeedingEvents(hass, "entry", "device", "Feeder 1")
    t.store.async_load = AsyncMock(return_value=cursor)
    t.store.async_save = AsyncMock()
    return t


async def test_baseline_duplicate_restart_and_new_mcu_boot(hass):
    events = []
    hass.bus.async_listen(EVENT_SCHEDULED_FEEDING, lambda e: events.append(e.data))
    t = await tracker(hass)
    await t.async_process(envelope(4))  # Connecting to an existing device is not a new meal.
    await hass.async_block_till_done()
    assert not events
    await t.async_process(envelope(5))
    await t.async_process(envelope(5))
    await hass.async_block_till_done()
    assert len(events) == 1
    assert events[0]["source"] == "mcu_scheduled_row"
    assert events[0]["meal"]["weekdays"] == 4
    assert events[0]["physical_delivery_confirmed"] is False
    resumed = await tracker(hass, copy.deepcopy(t.cursor))
    await resumed.async_process(envelope(5))
    await hass.async_block_till_done()
    assert len(events) == 1
    new_boot = envelope(1)
    new_boot["boot_id"] = "f" * 32
    await resumed.async_process(new_boot)
    await hass.async_block_till_done()
    assert len(events) == 2 and events[-1]["event_id"] != events[0]["event_id"]


async def test_old_reports_advance_cursor_without_emitting(hass):
    events = []
    hass.bus.async_listen(EVENT_SCHEDULED_FEEDING, lambda e: events.append(e.data))
    t = await tracker(hass, {"boot_id": BOOT, "sequence": 1})
    await t.async_process(envelope(2, age=120001))
    await hass.async_block_till_done()
    assert not events and t.cursor["sequence"] == 2


@pytest.mark.parametrize(
    "change",
    [
        {"boot_id": "bad"},
        {"sequence": True},
        {"sequence": -1},
        {"events": "wrong"},
        {"events": [None]},
        {"events": [{"sequence": 2, "age_ms": -1}]},
        {
            "events": [
                {
                    "sequence": 1,
                    "age_ms": 0,
                    "meal": {"weekdays": 1, "hour": 8, "minute": 0, "portions": 1, "enabled": False},
                }
            ]
        },
    ],
)
async def test_invalid_telemetry_cannot_create_an_event(hass, change):
    t = await tracker(hass)
    with pytest.raises((ValueError, KeyError, TypeError)):
        await t.async_process({**envelope(1), **change})
    t.store.async_save.assert_not_awaited()


async def test_storage_failure_prevents_emission_and_cursor_regression_is_rejected(hass):
    t = await tracker(hass, {"boot_id": BOOT, "sequence": 2})
    with pytest.raises(ValueError):
        await t.async_process(envelope(1))
    t.store.async_save.side_effect = OSError("disk unavailable")
    with pytest.raises(OSError):
        await t.async_process(envelope(3))
    assert t.cursor["sequence"] == 2


async def test_real_coordinator_polls_the_passive_endpoint(hass, entry, client):
    from .conftest import INFO

    client.async_get_info.return_value = {**INFO, "scheduled_feed_events": True}
    client.async_get_events.return_value = envelope()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    client.async_get_events.assert_awaited_once()
    client.async_feed.assert_not_awaited()
    client.async_set_schedule.assert_not_awaited()
    client.async_get_events.return_value = envelope(1)
    events = []
    hass.bus.async_listen(EVENT_SCHEDULED_FEEDING, lambda e: events.append(e.data))
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert len(events) == 1
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_event_api_is_get_only():
    from custom_components.pet_feeder_local.api import FeederClient

    from .test_api import Response, Session

    session = Session(Response(data=envelope()))
    client = FeederClient(session, "http://feeder.local:8080", "test-token")
    assert await client.async_get_events() == envelope()
    assert session.calls[0][0] == ("GET", "http://feeder.local:8080/api/v1/events")
