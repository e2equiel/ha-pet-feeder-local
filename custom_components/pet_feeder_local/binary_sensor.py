"""MCU connectivity comes from observed serial responses."""
from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.helpers.entity import EntityCategory
from .entity import FeederEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([McuSensor(entry.runtime_data)])


class McuSensor(FeederEntity, BinarySensorEntity):
    _attr_name = "MCU connection"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator):
        super().__init__(coordinator, "mcu")

    @property
    def is_on(self):
        return self.coordinator.data["status"]["mcu_connected"]
