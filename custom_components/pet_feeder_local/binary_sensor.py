"""MCU connectivity comes from observed serial responses."""
from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FeederConfigEntry
from .coordinator import FeederCoordinator
from .entity import FeederEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(hass: HomeAssistant, entry: FeederConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([McuSensor(entry.runtime_data)])


class McuSensor(FeederEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: FeederCoordinator) -> None:
        super().__init__(coordinator, "mcu")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data["status"]["mcu_connected"]
