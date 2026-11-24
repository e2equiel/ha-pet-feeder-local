"""Common typed coordinator entity and device metadata."""
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FeederCoordinator


class FeederEntity(CoordinatorEntity[FeederCoordinator]):
    """One entity of the feeder owned by this config entry."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: FeederCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.info['id']}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.info["id"])},
            name="Pet Feeder Local", manufacturer="Pet Feeder Local",
            model=coordinator.info["model"], sw_version=coordinator.info["version"],
        )
