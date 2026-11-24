"""Common device metadata."""
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN


class FeederEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.info['id']}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.info["id"])},
            name="Pet Feeder Local", manufacturer="Pet Feeder Local",
            model=coordinator.info["model"], sw_version=coordinator.info["version"],
        )
