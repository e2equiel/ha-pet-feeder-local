"""A separate explicit Serve action."""
from homeassistant.components.button import ButtonEntity
from .entity import FeederEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([ServeButton(entry.runtime_data)])


class ServeButton(FeederEntity, ButtonEntity):
    _attr_name = "Serve"
    _attr_icon = "mdi:food-drumstick"

    def __init__(self, coordinator):
        super().__init__(coordinator, "serve")

    @property
    def available(self):
        return super().available and self.coordinator.info.get("feeding_enabled", False)

    async def async_press(self):
        await self.coordinator.async_serve()
