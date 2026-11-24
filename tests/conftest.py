"""Reusable synthetic device fixture; real hardware and cloud are never used."""
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.pet_feeder_local.api import Schedule

INFO={"api_version":1,"id":"synthetic-device","model":"V330L-DU4L-VS","version":"0.2.0","feeding_enabled":True,"rtsp_port":8555}
STATUS={"mcu_connected":True,"serial_fault":False,"clock_synced":True,"manual_commands_sent":0}
DATA={"address":"http://192.168.1.123:8080","token":"synthetic-private-token","stream_source":""}

@pytest.fixture
def entry(hass):
    entry=MockConfigEntry(domain="pet_feeder_local",unique_id=INFO["id"],data=DATA,title="Pet Feeder Local")
    entry.add_to_hass(hass)
    return entry

@pytest.fixture
def client():
    with patch("custom_components.pet_feeder_local.FeederClient",autospec=True) as factory:
        client=factory.return_value
        client.async_get_info.return_value=INFO.copy()
        client.async_get_status.return_value=STATUS.copy()
        client.async_get_schedule.return_value=Schedule("12345678",())
        client.async_set_schedule.return_value=Schedule("87654321",())
        yield client

@pytest.fixture(autouse=True)
def ffmpeg_version():
    with patch("homeassistant.components.ffmpeg.FFVersion.get_version",return_value="6.0"):
        yield
