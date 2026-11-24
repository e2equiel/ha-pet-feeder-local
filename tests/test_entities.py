"""Behavior tests against Home Assistant 2026.11 entities."""
from datetime import datetime, UTC
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from zoneinfo import ZoneInfo

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util
from custom_components.pet_feeder_local.api import FeedOutcomeUnknown, Meal, Schedule
from custom_components.pet_feeder_local.button import ServeButton
from custom_components.pet_feeder_local.calendar import MealCalendar
from custom_components.pet_feeder_local.camera import FeederCamera
from custom_components.pet_feeder_local.coordinator import FeederCoordinator
from custom_components.pet_feeder_local.number import PortionNumber


def coordinator(meals=()):
    return SimpleNamespace(
        info={"id":"synthetic-device","model":"V330L-DU4L-VS","version":"test","feeding_enabled":True},
        selected_portions=1, last_update_success=True, mcu_ready=True,
        schedule=Schedule("12345678",meals), async_serve=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_portion_selection_does_not_serve():
    data = coordinator()
    number = PortionNumber(data)
    number.async_write_ha_state = Mock()
    await number.async_set_native_value(3)
    assert number.native_value == 3
    assert number.mode == "box"
    data.async_serve.assert_not_awaited()
    button = ServeButton(data)
    await button.async_press()
    data.async_serve.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_invalid_portion_selection_cannot_change_state():
    data = coordinator()
    number = PortionNumber(data)
    number.async_write_ha_state = Mock()
    for value in [0,11,1.5]:
        with pytest.raises(HomeAssistantError):
            await number.async_set_native_value(value)
    assert data.selected_portions == 1
    data.async_serve.assert_not_awaited()


@pytest.mark.asyncio
async def test_calendar_uses_mcu_weekday_bits_and_ignores_disabled_rows(monkeypatch):
    zone = ZoneInfo("America/Argentina/Buenos_Aires")
    dt_util.set_default_time_zone(zone)
    data = coordinator((Meal(1,8,30,2,True),Meal(127,9,0,1,False)))
    calendar = MealCalendar(data)
    events = await calendar.async_get_events(None,datetime(2026,11,22,tzinfo=zone),
                                             datetime(2026,11,24,tzinfo=zone))
    dt_util.set_default_time_zone(UTC)
    assert len(events) == 1
    assert events[0].start == datetime(2026,11,22,8,30,tzinfo=zone)
    assert events[0].summary == "2 portions"
    assert events[0].start.tzinfo == zone


@pytest.mark.asyncio
async def test_camera_uses_own_authenticated_rtsp():
    camera = FeederCamera(coordinator(),{"address":"http://feeder.local:8080","token":"synthetic-token"})
    assert await camera.stream_source() == "rtsp://feeder:synthetic-token@feeder.local:8555/live"
    assert camera.stream_options["rtsp_transport"] == "tcp"


@pytest.mark.asyncio
async def test_camera_can_share_a_local_restream_with_frigate():
    camera = FeederCamera(coordinator(),{"address":"http://feeder.local:8080","token":"synthetic-token",
                                          "stream_source":"rtsp://restream.local:8554/feeder"})
    assert await camera.stream_source() == "rtsp://restream.local:8554/feeder"


