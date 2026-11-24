"""Authenticated native RTSP camera. No Tuya stream acquisition."""
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote, urlsplit

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.components.ffmpeg import async_get_image
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FeederConfigEntry
from .const import CONF_ADDRESS, CONF_STREAM_SOURCE, CONF_TOKEN
from .coordinator import FeederCoordinator
from .entity import FeederEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(hass: HomeAssistant, entry: FeederConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([FeederCamera(entry.runtime_data, entry.data)])


class FeederCamera(FeederEntity, Camera):
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(self, coordinator: FeederCoordinator, config: Mapping[str, Any]) -> None:
        Camera.__init__(self)
        FeederEntity.__init__(self, coordinator, "camera")
        host = urlsplit(config[CONF_ADDRESS]).hostname
        port = coordinator.info.get("rtsp_port", 8555)
        self._source = config.get(CONF_STREAM_SOURCE) or f"rtsp://feeder:{quote(config[CONF_TOKEN], safe='')}@{host}:{port}/live"
        self.stream_options = {"rtsp_transport": "tcp"}

    @property
    def use_stream_for_stills(self) -> bool:
        """Reuse HA's stream worker instead of opening a second RTSP reader."""
        return True

    async def stream_source(self) -> str:
        return str(self._source)

    async def async_camera_image(self, width: int | None = None, height: int | None = None) -> bytes | None:
        return await async_get_image(self.hass, self._source,
                                     extra_cmd="-rtsp_transport tcp", width=width, height=height)
