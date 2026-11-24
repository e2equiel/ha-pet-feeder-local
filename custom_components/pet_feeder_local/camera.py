"""Authenticated native RTSP camera. No Tuya stream acquisition."""
from urllib.parse import quote, urlsplit
from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.components.ffmpeg import async_get_image
from .const import CONF_ADDRESS, CONF_TOKEN, CONF_STREAM_SOURCE
from .entity import FeederEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([FeederCamera(entry.runtime_data, entry.data)])


class FeederCamera(FeederEntity, Camera):
    _attr_name = "Camera"
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(self, coordinator, config):
        Camera.__init__(self)
        FeederEntity.__init__(self, coordinator, "camera")
        host = urlsplit(config[CONF_ADDRESS]).hostname
        port = coordinator.info.get("rtsp_port", 8555)
        self._source = config.get(CONF_STREAM_SOURCE) or f"rtsp://feeder:{quote(config[CONF_TOKEN], safe='')}@{host}:{port}/live"
        self.stream_options = {"rtsp_transport": "tcp"}

    async def stream_source(self):
        return self._source

    async def async_camera_image(self, width=None, height=None):
        return await async_get_image(self.hass, self._source,
                                     extra_cmd="-rtsp_transport tcp", width=width, height=height)
